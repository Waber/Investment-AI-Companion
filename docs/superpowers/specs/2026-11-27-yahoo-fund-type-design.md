# Yahoo instrument type and fund attributes (issue #153)

## Why

`fetch-company` stores every ticker as `STOCK`, so VWCE.DE gets the
stock score and no TER or AUM. Przemek wants real ETFs to get the fund
score from fetched data.

## What Yahoo returns (manual probe, 2026-11-27, not a test)

| Ticker | `quoteType` | TER field | `totalAssets` | `financialCurrency` | `fundFamily` |
| --- | --- | --- | --- | --- | --- |
| VWCE.DE | ETF | missing | 88.8e9 | missing | Vanguard Group (Ireland) Limited |
| IWDA.AS, EUNL.DE | ETF | `netExpenseRatio` 0.2 | missing | missing | BlackRock ... |
| SPY | ETF | `netExpenseRatio` 0.0945 | 796.9e9 | USD | State Street ... |
| ETFBW20TR.WA | ETF | missing | missing | missing | missing |
| 4GLD.DE, PHAU.L, SGLN.L (ETCs) | EQUITY | missing | missing | missing | missing |
| AAPL | EQUITY | | | USD | |

- `netExpenseRatio` is a percent: SPY's 0.0945 is 0.0945%.
- Yahoo labels ETCs `EQUITY` and gives no field that tells them from a
  stock.
- No field for distribution policy, domicile, replication, or
  underlying.

## Decisions

1. The company dict gains `instrument_type`: Yahoo `EQUITY` is
   `STOCK`, `ETF` is `ETF`, anything else is `None`. The fake returns
   `STOCK` for stocks and `ETF` or `ETC` for its funds.
2. Create uses that type. `None` stays `STOCK`, as today.
3. A refresh may change a stored `STOCK` to `ETF` or `ETC` when the
   provider says so. It never changes a stored `ETF` or `ETC`. An ETC
   is set by hand on the edit form, and a refresh keeps it.
4. `YahooFinanceCollector.fetch_fund_attributes` returns `None` unless
   `quoteType` is `ETF`. TER is `netExpenseRatio / 100` (a fraction,
   as stored). AUM is `totalAssets` only when `financialCurrency` is
   present. Without a currency the amount is dropped, because the
   score reads AUM only in EUR or USD and a guessed currency would be
   wrong data. Issuer is `fundFamily`. The other facts are null.
   `as_of` and `aum_as_of` are the retrieval date: Yahoo gives the
   current value without a date.
5. `fetch-company` fetches fund attributes for an ETF or an ETC and
   upserts the collector's row (`FundAttributesRepository.
   upsert_collected`). A manual, demo, or fixture row is kept. Every
   fact column is rewritten on refresh, like the TTM metrics row. A
   snapshot with no facts stores nothing.
6. The company is already saved when attributes are fetched. A
   provider error or bad provider data there does not fail the
   request. The response says what happened in `fund_attributes`:
   `created`, `updated`, `kept`, `unavailable`, or null (not a fund).
   It also returns `instrument_type`.

## Review decisions (2026-11-27)

- A fact that fails `FundAttributesCreate` (for example an issuer with
  a newline or over 255 characters) drops the whole snapshot, TER and
  AUM included, and the response says `unavailable`. The collector
  does not clean provider text itself; one set of checks stays at the
  boundary.
- Code review round 1 (F2), Przemek's decision: Yahoo gives no AUM at
  all. `totalAssets` has no date, and the score treats an undated AUM
  as no data (`app/instrument_score.py`). This replaces decision 4's
  AUM rule and the `GBp` check. `provenance.as_of` is None; the row's
  `as_of` falls back to the retrieval date, which says when the row
  was checked.
- Code review round 1 (F3): `provider_error` is its own status, and a
  row from another source answers `kept` without asking the provider.
- Code review round 1 (F1): the instrument page shows a collector
  row's source (`yahoo_finance`) instead of "no data".
- A refresh turns any stored `STOCK` into a fund type, including a
  `STOCK` the owner chose. The app cannot tell the two apart, and an
  ETF stored as a stock is the common case.
- The source check and the write in `upsert_collected` are not atomic.
  That matters only with concurrent writers (server phase), tracked
  in #161.

## Not in this change

- Telling an ETC from a stock automatically.
- Refusing a fund in `fetch-financial-metrics` from the provider's own
  `quoteType`. The stored type now comes from Yahoo, and a refresh
  fixes a mistyped ETF, so the stored-type check covers it.
- Mutual funds, indices, and other quote types stay `STOCK` on create,
  as today.
- AUM as `Decimal` (#142).
