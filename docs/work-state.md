# Current Work State

## Watchlist `/ui` page (#96): 2026-10-27

- Branch `feat/watchlist-ui-96`, from `origin/master` `b871326`.
  Pull request to `master`, Closes #96. Not merged.
- Design: `docs/superpowers/specs/2026-10-27-watchlist-ui-design.md`.
  Plan: `docs/superpowers/plans/2026-10-27-watchlist-ui.md`. Raul
  approved the design and chose the table layout.
- Completed: `/ui/watchlist` (nav link "Watchlista" / "Watchlist")
  lists company, ticker and label, latest close with currency, change
  against the previous bar, a 3-month sparkline (inline SVG, 92 days
  ending on the latest bar), the latest bar date with its source, a
  stale badge, and a remove button. The detail page has a heart
  toggle (♡/♥, `aria-pressed`). Add and remove are POST forms that
  HTMX enhances (`POST /ui/watchlist/{id}` and `.../remove`, hidden
  `from` = `detail` or `watchlist`). Prices are formatted from
  `Decimal` (`format_price`, 2 to 4 decimals, up to 8 for a price
  below 0.0001). `PriceBarRepository.recent_closes` reads the default
  series and skips bars without a close.
- Decisions: "stale" counts from today's UTC date (Raul), so every
  demo-v2 row with prices is stale (the fixture ends 2026-09-28). The
  column is "Zmiana" / "Change", not "daily", because demo bars are
  weekly. The demo starts with an empty watchlist; the demo script
  adds two instruments. A missing price, change, or trend is an em
  dash with the "no data" text as its title.
- Not in scope: named lists (#99), on-demand AI summary per row
  (#100), entering or editing the label.
- Tests: no `.env`, `DATABASE_URL` and `SECRET_KEY` unset. CI command
  on local SQLite 3.54.1: 1868 passed, 2 failed, 221 deselected,
  coverage 96.39%. The two failures are the known `0006` float
  boundary tests (below). Demo check: demo-v2 seeded into a
  throwaway SQLite file; four companies added through the heart
  POST; the table showed prices, sparklines, stale badges, sources,
  and no `style=` attribute. No local PostgreSQL; GitHub Actions runs
  both jobs. No live market-data calls. black, isort, and flake8
  passed on the changed Python files.
- Active agents: none. Blockers: none. Account usage was not
  available in this session.
- Next action: GitHub Actions on the pull request, then QA and Code
  Reviewer. Raul merges with "Rebase and merge".

## Open work elsewhere

- #33: notes and theses are on master (revision `0005`). Master's
  work-state still lists the `/ui` forms and any HTTP API as
  incomplete. Those belong to the Frontend Developer.
- #32: the watchlist backend is on master (revision `0004`).
  The `/ui` page is #96, on `feat/watchlist-ui-96`.
- #8 and #10: the instrument Alembic baseline is still open,
  and `init_db` still uses `create_all`.
- #54: the real Yahoo adapter, and the case where a Yahoo HTTP
  failure looks like "no data", stay on #54. Post-demo work
  runs from #54 through #58.
- #26: instrument type and ISIN are on master. Master's
  work-state still records that the shipped `/ui` used
  lowercase `stock` and did not show `isin` before the later
  form work.
- #34: company and financial-metrics forms. ETF/ETC attribute
  forms stay on #28. A `source=manual` column and a synthetic
  marker that survives a description edit are still open there.
- Demo-v1 price profiles: `run_demo` loads demo-v2, and the
  manual `seed_demo` steps stay demo-v1 unless
  `--fixture demo-v2`. The fake collector still serves demo-v1
  price profiles. The `/ui` synthetic badge labels
  `[IAC-DEMO-V1]` as `demo-v1` and `[IAC-DEMO-V2]` as `demo-v2`
  (`demo_source_label` in `app/ui/view_models.py`).
- #99: named watchlists (several lists per company).
- #100: on-demand AI summary of recent moves in a watchlist row.
- #86: the shared validator is on master (#98). The `/ui` helper
  (`normalized_company_name` in `app/ui/form_fields.py`) moves
  onto it with the Frontend Developer, and the form maps
  `exc.code` to a catalog key. A name made only of combining
  marks is still rejected by the form and accepted by the API.
- #28: ETF/ETC attribute columns, fund attributes, and the
  attribute forms. Yahoo still does not implement
  `FundAttributes`.
- Local SQLite 3.54 casts a float to text with more digits than
  the SQLite in CI. Two `0006` boundary tests fail locally on
  `master` for that reason. Not tracked in an issue yet.
- #57, #58, and #65 are open post-demo issues. #57 is
  portfolio holdings (model, manual or CSV import, privacy).
  #58 is the market scanner and buy, sell, and opportunity
  signals. #65 is the AI Portfolio, after real portfolios and
  signals. None of them is on this branch.
- #27 is still open. PR #83 merged on 2026-10-21 and its body
  says Refs #27. Price-bar storage and the demo-v2 fixture
  landed in that pull request. ETF and ETC attribute columns
  stay on #28, which is still open, so #83 did not close #27.
- #95 is open. It lists follow-ups for #94: skipped bars, a
  duplicate `(date, source)` inside one batch, a lighter tie
  query, an optional cap on the log-once sets, and currency
  length on SQLite. #94 merged on 2026-10-22 (revision
  `0006`).
- Tooling: `.github/workflows/tests.yml` runs the two pytest
  jobs only. The workflow says neither job lints, so CI does
  not run black, isort, or flake8. `setup_database.py` fails
  flake8: unused `Session` (line 14) and unused `engine`
  (line 19), and E402 on lines 19 and 20 because those
  imports follow the `sys.path` change.
- Dependencies: `google-genai` is not pinned. It waits for
  the Gemini adapter (README and product requirements). PyPI
  `google-genai` 2.32.0, checked 2026-10-22, requires
  `websockets<17.0,>=13.0.0`. `requirements-dev.lock` pins
  `websockets==17.2`, so installing `google-genai` would
  downgrade `websockets`. `jinja2` is already pinned at
  3.1.6.
