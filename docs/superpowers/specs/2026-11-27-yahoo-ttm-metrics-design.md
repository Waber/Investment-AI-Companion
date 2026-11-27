# Real stock metrics from Yahoo (TTM snapshot): design

- Date: 2026-11-27. Owner: Przemek. Refs #54, #35.
- Status: approach A approved by Przemek on 2026-11-27.

## Why

Przemek wants to use the app himself on real data as soon as
possible. A real stock fetched from Yahoo has a company row and price
bars, but its score covers `0 of 4` components:
`POST /api/v1/data-collection/fetch-financial-metrics` is a
placeholder, so no financial metrics are stored. The collector already
reads every figure the stock score needs from Yahoo `info`.

## Goal

One call stores a real stock's latest Yahoo ratios, so
`GET /api/v1/instruments/{id}/score` scores all four stock components
when Yahoo has the data.

Non-goals: annual and quarterly history from the statements (approach
B, later, with the trend charts); ETF and ETC typing and fund
attributes; a longer price window; any `/ui` change (UI waits for the
UI agent).

Anti-goals: a missing value stored as 0; provider text in a response
or a log; a manual row overwritten by a fetch; a network call in an
automated test.

## Approaches

- **A. TTM snapshot from `info` (chosen).** One row per fetch,
  `period_type="ttm"`, dated by Yahoo's `mostRecentQuarter`. Fastest
  path to a working score. Trade-offs: Yahoo's own ratio definitions;
  P/E and P/B use today's price but the row carries the quarter-end
  date; history starts with the first fetch.
- **B. Annual and quarterly rows from the statements.** Transparent
  ratios and about four years of history, but P/E and P/B need shares
  and price, GPW statements on Yahoo are often incomplete, and it is
  two to three times the work.
- **C. A now, B later.** This is what Przemek picked: A now, B when the
  trend charts come.

## Design

1. **Collector.** `YahooFinanceCollector.fetch_key_metrics` puts
   `mostRecentQuarter` (Unix seconds) into `Provenance.as_of` as a UTC
   date. A missing or unreadable value leaves `as_of` as `None`. The
   fake collector already sets `as_of`.
2. **Sources.** `RECORD_SOURCES` gains the two collector names,
   `yahoo_finance` and `fake`. The stored row's `source` is the
   provenance source. (Agent's call: the allow-list comment already
   says a new source needs no migration.)
3. **Mapping** from `KEY_METRIC_FIELDS` to `financial_metrics`:
   `roe`, `roa`, `gross_margin`, `current_ratio`, `quick_ratio`,
   `debt_to_equity`, `debt_to_assets`, `revenue_growth`, `pe_ratio`,
   `pb_ratio`, `ev_ebitda` by the same name, and `profit_margin` to
   `net_margin`. A value that is not a finite number is `None`. Units
   stay Yahoo's, which are the units `docs/scoring.md` already uses
   (fractions; debt-to-equity in percent).
4. **Row key.** `period_type="ttm"`, `period_end` = `as_of` at 00:00
   UTC. The unique key is still company, `period_end`, `period_type`.
5. **Write rule.** No row for that key: create it. A row whose source
   is the same collector: replace all mapped fields with the new
   snapshot. A row with any other source (for example `manual`): 409,
   nothing changes.
6. **Endpoint.** `POST /api/v1/data-collection/fetch-financial-metrics`
   with `{"ticker": ...}` (the existing request model) returns the
   stored row as `FinancialMetrics`.
   - The company is not in the database: 404 (fetch the company
     first).
   - The instrument is not a `STOCK`: 400. (Agent's call: the fund
     score does not read these rows, and fund ratios from `info` would
     mislead.)
   - The provider returns nothing, no `as_of`, or none of the seven
     score figures: 404 no data. Never zeros.
   - `ProviderError` or an unexpected error: 502 with the fixed
     `Data provider error` detail, class name only in the log, the way
     `fetch-company` does it.
7. **Docs.** `docs/api-demo.md` describes the route. Journal and work
   state as usual.

## Tests (offline only)

- Collector: `mostRecentQuarter` becomes `as_of`; missing or bad
  values give `None`.
- Route, with a fake collector through `dependency_overrides`: create,
  refresh in the same quarter (one row, new values), a new quarter (a
  second row), a manual row on the same key (409, unchanged), unknown
  company (404), ETF (400), no data and no `as_of` (404), NaN to
  `None`, provider error (502, no provider text).
- Score: after the fetch, a stock with all seven figures scores
  `4 of 4`.
- Manual check after merge-ready: the same probe against real Yahoo
  (AAPL, PKN.WA), not an automated test.

## Left to the builder

Names of helpers and tests, where the mapping lives, and the exact
404/400/409 messages.
