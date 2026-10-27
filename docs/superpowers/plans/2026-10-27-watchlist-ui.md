# Watchlist `/ui` Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `/ui/watchlist` table page and a heart toggle on the instrument detail page, built on the merged watchlist backend (#90) and price bars (#94).

**Architecture:** A repository method reads the recent closes of the default price series. A UI module turns watchlist rows plus those closes into frozen view objects (Decimal values, sparkline points, stale flag). Jinja2 templates render them. Add and remove are plain POST forms that HTMX enhances by swapping a fragment.

**Tech Stack:** FastAPI, SQLAlchemy, Jinja2, HTMX 2.0.10 (bundled), pytest + httpx `AsyncClient`.

**Spec:** `docs/superpowers/specs/2026-10-27-watchlist-ui-design.md`

## Global Constraints

- Branch `feat/watchlist-ui-96`. Rebase onto `origin/master`, never merge it in.
- Prices are `Decimal`. Text shown to the user is formatted from `Decimal`, never through `float`. Only sparkline pixel coordinates may use `float`.
- CSP stays `default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`. No `style=` attributes, no inline `<script>`, no remote assets. Colours come from classes in `static/ui.css`.
- Every new string is in both `_POLISH` and `_ENGLISH` in `app/ui/catalog.py` (a test checks the key sets match).
- No new "not investment advice" copy.
- Stale rule: latest bar date `< today_utc - WATCHLIST_STALE_PRICE_DAYS days` (strictly more than N days old). "Today" is the UTC date.
- Trend window: bars with `bar_date >= latest_date - 92 days` (about 3 months), ending at the latest bar, not at today. (Plan's call: 92 days instead of calendar months.)
- Bars with `close_price IS NULL` are ignored everywhere on the page.
- Tests never call live market-data providers. Run with `DATABASE_URL` and `SECRET_KEY` unset.

## Review Focus

1. A price below 0.0001 (penny instruments, crypto pairs) must not show as `0,0000`. Expect up to 8 decimals when 4 would round a non-zero value to zero. Test in Task 1.
2. A flat series (every close equal) must still draw a sparkline (a horizontal line in the middle), not divide by zero. Test in Task 3.
3. Removing a company that exists but is not listed (double click, second tab) is not an error: 303, or the fragment with the "not listed" state. Test in Task 5.
4. A bar exactly `WATCHLIST_STALE_PRICE_DAYS` days old is not stale; one day more is. Test in Task 3.
5. An HTMX add/remove for an unknown id is the HTML 404 and HTMX does not swap it in (the existing htmx-config). Test in Task 5 asserts 404 with an `HX-Request` header.

---

### Task 1: Decimal price, percent, and date formatters

**Files:**
- Modify: `app/ui/formatting.py`
- Modify: `app/ui/templating.py` (register the new functions as Jinja globals, next to `format_date`)
- Test: `tests/test_ui_formatting.py`

**Interfaces:**
- Produces: `format_price(value: Decimal | None, language: str) -> str | None`, `format_change(value: Decimal | None, language: str) -> str | None`, `format_day(value: date | None, language: str) -> str | None`. All three are Jinja globals.

- [ ] **Step 1: Write the failing tests**

```python
from datetime import date
from decimal import Decimal
from app.ui.formatting import format_change, format_day, format_price

def test_price_keeps_two_to_four_decimals_from_decimal():
    assert format_price(Decimal("227.50000000"), "pl") == "227,50"
    assert format_price(Decimal("7.37600000"), "pl") == "7,376"
    assert format_price(Decimal("3487.97090000"), "pl") == "3 487,9709"
    assert format_price(Decimal("3487.97090000"), "en") == "3,487.9709"
    assert format_price(Decimal("1.23456789"), "en") == "1.2346"  # half-even in Decimal
    assert format_price(None, "pl") is None

def test_tiny_price_is_not_shown_as_zero():
    assert format_price(Decimal("0.00001234"), "en") == "0.00001234"
    assert format_price(Decimal("0E-8"), "en") == "0.00"

def test_price_never_goes_through_float():
    # 999999999999.99999999 is not representable as a float.
    assert format_price(Decimal("999999999999.99999999"), "en") == "999,999,999,999.99999999"

def test_change_has_a_sign_and_two_decimals():
    assert format_change(Decimal("1.2449"), "pl") == "+1,24"
    assert format_change(Decimal("-0.625"), "en") == "-0.62"  # half-even
    assert format_change(Decimal("0"), "en") == "0.00"
    assert format_change(None, "en") is None

def test_day_formats_a_date():
    assert format_day(date(2026, 9, 28), "pl") == "28.09.2026"
    assert format_day(date(2026, 9, 28), "en") == "Sep 28, 2026"
    assert format_day(None, "pl") is None
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_ui_formatting.py -q` — expect ImportError for the new names.

- [ ] **Step 3: Implement the three functions in `app/ui/formatting.py`**

Reuse `_NUMBER_SEPARATORS` and `_ENGLISH_MONTHS`. `format_price`: quantize to 4 places with `ROUND_HALF_EVEN`; if that is zero but the value is not, keep the value's own digits (up to 8 places, trailing zeros stripped); otherwise strip trailing zeros past the second decimal. Group thousands on the integer digits as text. `format_change`: quantize to 2 places half-even, `+` for positive, `-` for negative, no sign for zero. `format_day` mirrors `format_date` for a `date`.

- [ ] **Step 4: Run** the same command — expect PASS. Also run `tests/test_ui_templates.py -q`.

- [ ] **Step 5: Commit** `feat: format Decimal prices and changes for the watchlist`

### Task 2: Recent closes of the default price series

**Files:**
- Modify: `app/repositories/price_bar_repository.py`
- Test: `tests/test_price_bars.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class RecentCloses:
      source: str
      latest: PriceBarDB            # newest bar with a close
      previous: PriceBarDB | None   # the bar with a close just before latest, may be older than the window
      window: list[PriceBarDB]      # bars with a close, bar_date >= latest.bar_date - window_days, oldest first, includes latest

  def recent_closes(self, instrument_id: int, window_days: int = 92) -> RecentCloses | None
  ```
  `None` when the default series has no bar with a close (or no bars at all).

- [ ] **Step 1: Write the failing tests** (session-level, using the `client` fixture's `testing_session_local` like the other tests in this file)

  - `test_recent_closes_window_and_previous`: weekly bars 2026-06-01 … 2026-09-28 with closes; assert `latest.bar_date == date(2026, 9, 28)`, `previous.bar_date == date(2026, 9, 21)`, `window[0].bar_date >= date(2026, 6, 28)`, window is oldest first and ends with latest.
  - `test_recent_closes_skips_null_close`: the newest bar has `close_price=None`; `latest` is the bar before it.
  - `test_recent_closes_uses_the_default_source`: two sources, the later `retrieved_at` wins (same rule as `get_range`).
  - `test_recent_closes_none_without_closes`: no bars → `None`; bars that all have `close_price=None` → `None`.
  - `test_previous_can_be_older_than_the_window`: bars 2026-01-05 and 2026-09-28 only → `previous.bar_date == date(2026, 1, 5)`, `window` has one bar.

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_price_bars.py -q -k recent_closes` — expect AttributeError.

- [ ] **Step 3: Implement** with `_default_source` on the instrument's bars, then queries filtered by that source and `close_price IS NOT NULL`: one `ORDER BY bar_date DESC LIMIT 2` for latest/previous, one for the window. Drop rows with `_readable(row)` false, as `get_range` does.

- [ ] **Step 4: Run** the same command — expect PASS.

- [ ] **Step 5: Commit** `feat: read the recent closes of the default price series`

### Task 3: Watchlist view model and sparkline

**Files:**
- Create: `app/ui/watchlist_view.py`
- Test: `tests/test_ui_watchlist_view.py`

**Interfaces:**
- Consumes: `RecentCloses`, `PriceBarRepository.recent_closes` (Task 2), `WatchlistRepository.list_items`, `demo_source_label` / the synthetic rule from `app/ui/view_models.py`.
- Produces:
  ```python
  def utc_today() -> date   # tests monkeypatch app.ui.watchlist_view.utc_today

  @dataclass(frozen=True)
  class Sparkline:
      points: str        # "x,y x,y ..." for <polyline points>, viewBox 0 0 90 24
      direction: str     # "up" | "down" | "flat"

  @dataclass(frozen=True)
  class WatchlistEntryView:
      company_id: int
      name: str | None
      ticker: str | None
      label: str | None
      is_synthetic: bool
      close: Decimal | None
      currency: str | None
      change: Decimal | None         # percent, unrounded
      direction: str | None          # "up" | "down" | "flat" | None
      previous_date: date | None
      latest_date: date | None
      source: str | None             # the price series' source string
      is_stale: bool
      sparkline: Sparkline | None

  def sparkline(closes: list[Decimal], width: int = 90, height: int = 24) -> Sparkline | None
  def to_entry(item: WatchlistItemDB, recent: RecentCloses | None, today: date, stale_days: int) -> WatchlistEntryView
  def list_entries(db: Session, today: date | None = None) -> list[WatchlistEntryView]   # reads settings.WATCHLIST_STALE_PRICE_DAYS
  ```

- [ ] **Step 1: Write the failing tests**

  - `test_change_is_percent_against_previous_close`: closes 100 → 101.24 gives `change == Decimal("1.24")`, `direction == "up"`; previous close 0 gives `change is None`; no previous gives `change is None`.
  - `test_stale_boundary`: `today = date(2026, 10, 27)`, `stale_days = 7`: latest 2026-10-20 → `is_stale is False`; 2026-10-19 → `True`.
  - `test_no_prices_entry`: `recent=None` → `close`, `change`, `latest_date`, `sparkline` are `None`, `is_stale is False`.
  - `test_sparkline_scales_and_picks_direction`: `[1, 2, 3]` → three points, first x 0, last x 90, `direction == "up"`; a single close → `None`.
  - `test_flat_sparkline_is_a_middle_line`: `[5, 5, 5]` → every y is `12`, `direction == "flat"`.
  - `test_synthetic_company_is_flagged`: description starting `[IAC-DEMO-V2]` → `is_synthetic is True`.

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_ui_watchlist_view.py -q` — expect ImportError.

- [ ] **Step 3: Implement.** Change = `(latest - previous) / previous * 100` in `Decimal`. Sparkline y is inverted (higher price, smaller y) with 1px padding; round coordinates to one decimal. Direction compares the last close with the first close of the window. `list_entries` calls `recent_closes` once per item (N+1 is acceptable per the spec).

- [ ] **Step 4: Run** the same command — expect PASS.

- [ ] **Step 5: Commit** `feat: build watchlist rows with change, trend, and stale flag`

### Task 4: Watchlist page, nav link, strings, and styles

**Files:**
- Create: `app/ui/templates/watchlist.html`, `app/ui/templates/partials/watchlist_table.html`
- Modify: `app/ui/router.py` (route `GET /ui/watchlist`), `app/ui/templates/base.html` (nav link), `app/ui/catalog.py`, `static/ui.css`
- Test: `tests/test_ui_watchlist.py` (new)

**Interfaces:**
- Consumes: `list_entries`, `utc_today` (Task 3); formatters (Task 1).
- Produces: template `partials/watchlist_table.html` that renders `entries` (the whole `<table>` or the empty state) with root element `id="watchlist-table"`. Task 5 swaps it.
- Catalog keys (PL / EN):
  - `nav.watchlist`: "Watchlista" / "Watchlist"
  - `page.watchlist_title`: "Watchlista" / "Watchlist"
  - `watchlist.empty`: "Watchlista jest pusta. Dodaj spółkę serduszkiem na jej stronie." / "Your watchlist is empty. Add a company with the heart on its page."
  - `watchlist.go_to_instruments`: "Przejdź do listy instrumentów" / "Go to the instrument list"
  - `column.company`: "Spółka" / "Company"; `column.price`: "Cena" / "Price"; `column.change`: "Zmiana" / "Change"; `column.trend`: "Trend 3 mies." / "3-month trend"; `column.latest_bar`: "Notowanie z" / "Price date"
  - `watchlist.change_since`: "wobec {date}" / "vs {date}" (rendered with `.replace("{date}", ...)`)
  - `watchlist.stale`: "nieaktualne" / "stale"; `watchlist.stale_hint`: "Notowanie starsze niż {days} dni" / "Price older than {days} days"
  - `watchlist.no_prices`: "brak notowań" / "no prices"
  - `watchlist.source`: "źródło: {source}" / "source: {source}"
  - `watchlist.add`: "Dodaj do watchlisty" / "Add to watchlist"; `watchlist.remove`: "Usuń z watchlisty" / "Remove from watchlist"

- [ ] **Step 1: Write the failing tests** (seed companies, watchlist rows, and bars through `client.app.state.testing_session_local`; monkeypatch `app.ui.watchlist_view.utc_today` to `date(2026, 10, 27)`)

  - `test_watchlist_lists_price_change_trend_and_date`: one company with bars 2026-10-19 (100) and 2026-10-26 (101.24) → page 200 contains `101,24`, `+1,24`, a `<polyline`, `26.10.2026`, a link to `/ui/instruments/{id}`, the stored label `long term`, no `nieaktualne`.
  - `test_watchlist_empty_state_links_to_instruments`: no rows → the `watchlist.empty` text and `href="/ui"`.
  - `test_watchlist_marks_a_stale_price`: latest bar 2026-09-28 → `nieaktualne`.
  - `test_watchlist_row_without_prices`: → `brak notowań`, no `<polyline`.
  - `test_watchlist_single_bar_has_no_change`: one bar → the price is shown, the change cell is the dash.
  - `test_watchlist_english_strings`: cookie `ui_lang=en` → "Watchlist", "Change", "stale", `Sep 28, 2026`.
  - `test_watchlist_shows_source_and_synthetic_badge`: `[IAC-DEMO-V2]` company and source → the source text and the `badge.synthetic` text.
  - `test_watchlist_headers_and_nav`: the CSP header is unchanged (reuse the assertions of `_assert_ui_headers` in `tests/test_ui_forms.py`), the nav contains `href="/ui/watchlist"`, and the HTML has no `style=` attribute.

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_ui_watchlist.py -q` — expect 404s / failures.

- [ ] **Step 3: Implement** the route (`list_entries(db, utc_today())`, `_with_ui_headers(render(...))`), templates following `instrument_list.html` and `metric_table.html` conventions (`data-field` on cells), the nav link, catalog keys, and CSS classes `.change-up`, `.change-down`, `.change-flat`, `.sparkline-up`/`-down`/`-flat` (stroke colour), `.badge-stale`, `.muted`, `.heart`, `.heart[aria-pressed="true"]`. Up/down cells show ▲ / ▼ before the number. A missing value uses the existing `t['missing']` dash.

- [ ] **Step 4: Run** `tests/test_ui_watchlist.py tests/test_ui_catalog.py tests/test_ui_templates.py tests/test_ui_pages.py -q` — expect PASS.

- [ ] **Step 5: Commit** `feat: add the watchlist page`

### Task 5: Add and remove (heart on the detail page, ✕ on the watchlist)

**Files:**
- Create: `app/ui/templates/partials/watchlist_heart.html`
- Modify: `app/ui/forms.py` (two POST routes), `app/ui/router.py` (`instrument_detail` passes `on_watchlist`), `app/ui/templates/instrument_detail.html`, `app/ui/templates/partials/watchlist_table.html`
- Test: `tests/test_ui_watchlist.py`

**Interfaces:**
- Consumes: `WatchlistRepository.add/remove/contains`, `_load_company`, `_see_other` in `forms.py`, `is_htmx` in `router.py`, `partials/watchlist_table.html` (Task 4).
- Produces: `POST /ui/watchlist/{company_id}` (add) and `POST /ui/watchlist/{company_id}/remove`. Form field `from` is `"detail"` or `"watchlist"` (anything else is treated as `"detail"`).
  - Plain POST: 303 to `/ui/instruments/{id}` (`from=detail`) or `/ui/watchlist` (`from=watchlist`).
  - HTMX POST: 200 with `partials/watchlist_heart.html` (`from=detail`) or `partials/watchlist_table.html` (`from=watchlist`).
  - Unknown or malformed id: the HTML 404 (via `_load_company`).
  - The heart is a `<form method="post" action="/ui/watchlist/{id}[/remove]" hx-post=... hx-target="this" hx-swap="outerHTML">` with a `<button>` that has `aria-pressed`, `aria-label`, and `title` = `watchlist.add` or `watchlist.remove`, showing ♡ or ♥. The ✕ is the same pattern with `hx-target="#watchlist-table"`.

- [ ] **Step 1: Write the failing tests**

  - `test_heart_adds_and_removes_with_plain_post`: POST add → 303 to the detail page, row stored; detail page shows `aria-pressed="true"`; POST remove → 303, row gone, `aria-pressed="false"`.
  - `test_heart_htmx_returns_the_fragment`: with `HX-Request: true` → 200, body is the heart form only (no `<html`), state flipped.
  - `test_repeat_add_keeps_the_label`: store a row with label `"long term"` via `WatchlistRepository`, POST add again → label unchanged.
  - `test_remove_from_watchlist_page_htmx_shows_empty_state`: last row removed with `from=watchlist` and HTMX → the `watchlist.empty` text in the fragment.
  - `test_remove_not_listed_is_not_an_error`: existing company, not listed → 303 (plain) and 200 fragment (HTMX).
  - `test_unknown_company_is_404_also_for_htmx`: id 999999 and `abc`, with and without `HX-Request` → 404.
  - `test_cross_origin_post_is_403`: `origin="http://evil.example"` → 403 (the router dependency).

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_ui_watchlist.py -q` — expect failures.

- [ ] **Step 3: Implement** the routes, the heart partial, the detail-page include next to the instrument name, and the ✕ form in each table row.

- [ ] **Step 4: Run** `tests/test_ui_watchlist.py tests/test_ui_forms.py tests/test_ui_origin.py tests/test_ui_pages.py -q` — expect PASS.

- [ ] **Step 5: Commit** `feat: add and remove watchlist companies from the UI`

### Task 6: Docs, demo check, and full verification

**Files:**
- Modify: `docs/work-state.md`, `docs/development-journal.md`, `docs/RUN_DEMO.md` (one line: the watchlist page and the heart), `docs/HANDOFF.md` (queue item a done)

- [ ] **Step 1:** Seed the demo on a throwaway SQLite file (`python -m scripts.run_demo` per `docs/RUN_DEMO.md`, or the seed command it documents) and load `/ui/watchlist` and one detail page with `httpx` against the running app, or with `TestClient`, to confirm the heart, the rows, and the stale markers render with demo-v2 data. Stop the server.
- [ ] **Step 2:** Full CI command: `env -u DATABASE_URL -u SECRET_KEY PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`. Expected: everything passes except the two known SQLite 3.54 failures in `tests/test_price_bar_migration.py` (recorded in `docs/work-state.md`).
- [ ] **Step 3:** `black --check`, `isort --check-only`, `flake8` on the changed Python files.
- [ ] **Step 4:** Update the docs (scope, decisions, verification, AI model, time). Commit `docs: record the watchlist page (#96)`.
