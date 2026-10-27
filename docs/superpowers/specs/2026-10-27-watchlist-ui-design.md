# Watchlist `/ui` page (#96): design

Date: 2026-10-27. Issue: #96 (UI part of #32). The backend merged in #90.
Follow-ups that are out of scope: #99 (named lists), #100 (on-demand AI
summary per row).

## Intent

Raul wants to keep a short list of companies he follows and see in one
glance how each one is doing: name, latest price, the last move in
percent, and a small trend line. He adds a company from its own page
with one click on a heart icon, so the screen does not fill up with
text buttons.

## Goals

- A heart toggle on the instrument detail page: an empty heart when the
  company is not on the watchlist, a full heart when it is. One click
  adds or removes it without a full page reload.
- A watchlist page at `/ui/watchlist`, linked from the header nav, laid
  out as a table (Raul picked the table over app-style rows). One row
  per watchlist item, in the repository order (oldest `added_at` first).
- Columns: company (name linked to `/ui/instruments/{id}`, ticker and
  the stored label underneath in muted text), latest close with its
  currency, change, trend sparkline, date of the latest bar with a
  stale marker, and a remove button (✕).
- PL and EN strings for everything new.
- The page works with the demo-v2 fixture on SQLite. The demo starts
  with an empty watchlist: the demo script in the product requirements
  (step 2:15) has the presenter add two instruments, so no fixture or
  seed change.

## Non-goals

- Several named lists (#99). The backend keeps `UNIQUE(company_id)`.
- Entering or editing the label. The label is shown when stored (API or
  a later change); this page has no label field.
- Sorting or filtering the watchlist.
- Any AI text on this page (#100).
- No new "not investment advice" copy (product requirements section 12).

## Anti-goals

- A price shown as a float or rounded through `float`. Prices are
  `Decimal` (#94) and must be formatted from `Decimal`.
- A stale price that looks fresh. Freshness is always visible.
- Remote assets, inline scripts, or anything that needs a CSP change.
  The page uses the bundled HTMX only.

## Data rules (decided with Raul)

- **Price series:** the default source per instrument, exactly as
  `PriceBarRepository.get_range` picks it with `source=None`.
- **Bars without a close** (`close_price` is nullable) are ignored
  everywhere on this page: for the latest close, the previous close,
  the stale date, and the sparkline points. A series whose bars all
  lack a close is shown like "no bars". *(Claude's call.)*
- **Latest close and its date:** the last bar of that series.
- **Price text:** formatted from `Decimal` with the PL/EN separators,
  at least 2 and at most 4 decimals, trailing zeros past the second
  removed (`227,50`, `7,376`, `3 487,9709`). A price below 0.1 keeps
  4 significant digits, up to 8 places (`0,001235`, `0,00006`), so a
  sub-cent price is not rounded to one digit. A value with more places
  is rounded half-even in `Decimal`. *(Claude's call; the sub-0.1 rule
  was added after the final review.)*
- **Source and synthetic data:** the date cell shows the series'
  source in muted text under the date, and the company cell shows the
  existing synthetic badge (`badge.synthetic`) when the company is
  synthetic, like the list and detail pages. AGENTS.md requires the
  source to be visible. *(Claude's call.)*
- **Change:** `(last close − previous close) / previous close × 100`,
  where "previous" is the bar before the last one in the same series.
  The column header is "Zmiana" / "Change", not "daily", because the
  demo data is weekly. The cell's `title` names the date of the
  previous bar, e.g. "vs 21.09.2026". Green ▲ for positive, red ▼ for
  negative, neutral for zero. One bar only, or a previous close of
  zero: show a dash. Compute with `Decimal` and show two decimals.
- **Trend:** the bars of that series from the last 3 months ending on
  the latest bar's date (not today). Two or more points draw a
  sparkline; fewer show a dash. Green when the last close is above the
  first point of the window, red when below, neutral when equal.
- **Stale marker:** the latest bar's date is more than
  `settings.WATCHLIST_STALE_PRICE_DAYS` (default 7) days before
  **today's date** (UTC). Raul decided to count from today, not from
  the fixture's `as_of`, so in the demo every row that has prices is
  marked until the fixture gets newer data. That is expected.
- **No bars:** price, change, and trend are dashes, the date cell says
  "no prices" / "brak notowań", no stale marker.

## Parts of the how already decided

- Server-rendered Jinja2 like the other `/ui` pages. Routes under the
  existing `/ui` routers, so `require_same_origin` covers every POST
  and `_with_ui_headers` sets the CSP and cache headers.
- The sparkline is inline SVG built on the server (a `<polyline>` with
  points scaled into a fixed viewBox). No chart library, no JS. Scaling
  may use `float` because it only places pixels; the numbers shown as
  text stay `Decimal`.
  The CSP (`default-src 'self'`) blocks inline `style` attributes, so
  colours come from classes in `static/ui.css`, not from `style=` or
  SVG presentation styles set inline by CSS text.
- Add and remove are HTML forms with `method="post"` so they work
  without JS, enhanced with `hx-post` so HTMX swaps only the heart (on
  the detail page) or the row/table (on the watchlist page). A plain
  POST answers with a 303 redirect back to the page it came from.
  Adding a company that is already listed keeps the original label
  (the repository's `add` is idempotent).
- The heart button has `aria-label` and `title` with the action text
  ("Dodaj do watchlisty" / "Usuń z watchlisty") and `aria-pressed`
  for the current state. Removing the last row shows the empty state.
- Empty state: one sentence telling the user to add companies with the
  heart on a company page, with a link to the instrument list.
- An unknown or deleted company on add or remove is the existing
  translated HTML 404.

## Left to the builder

- Route paths for add and remove, and whether the fragment templates
  live under `templates/partials/`.
- The view-model shape (`WatchlistEntryView` was the name used in
  `docs/HANDOFF.md`) and where the Decimal price formatter lives
  (`app/ui/formatting.py` has a float-based `format_number`; a new
  Decimal formatter with the same PL/EN separators fits there). A date
  formatter for `date` values is needed too; `format_date` takes a
  `datetime`.
- Query shape: N+1 per row is acceptable for a short list, but loading
  the window once per instrument (not every bar since 2022) is
  expected.
- CSS in `static/ui.css` following the existing palette.

## Done when

- UI tests (deterministic, no live providers) cover: the list with
  price, change, trend, and date; the empty state; the stale marker
  (freeze "today" in the test); a company with no bars; one bar only;
  add and remove through plain POST and through HTMX; a repeat add
  keeps the label; PL and EN strings; the CSP header is unchanged.
- `docs/work-state.md` and `docs/development-journal.md` updated.
- CI green on SQLite and PostgreSQL. QA, then Code Reviewer. Raul
  merges with "Rebase and merge".
