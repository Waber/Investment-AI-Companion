# Instrument score

The score is a number from 0 to 100. It is computed in Python from
figures that are already stored. It does not call a language model
and it does not call a market-data provider. Nothing in this number
is an instruction. The words for an instruction are not used in the
API text.

A total of `null` with status `no_score` means there was nothing
usable to add up. That is not a score of zero. A real zero is status
`scored` and total `"0.00"`.

The code is `app/scoring.py`. It does not open the database. The
route loads the rows and then calls `score_instrument`.

## What goes in

A stock uses four components. Each component can use more than one
stored column. The component score is the average of the input
scores that are usable. If only one of the two is usable, that one
is the component score.

| Component | Stored columns | What a high score means |
| --- | --- | --- |
| profitability | `roe`, `net_margin` | The business earns more |
| valuation | `pe_ratio`, `pb_ratio` | The price is less expensive |
| balance_sheet | `debt_to_equity`, `current_ratio` | Less debt, more short-term cover |
| growth | `revenue_growth` | Revenue is growing |

An ETF and an ETC use the same four components. Each type still has
its own weight row, so a change for ETFs does not change ETCs.

| Component | Stored figure | What a high score means |
| --- | --- | --- |
| cost | `ter` | The fee is lower |
| size | `aum` | The fund is larger |
| volatility | price-derived volatility | The path is calmer |
| max_drawdown | price-derived max drawdown | The worst fall is smaller |

Tracking difference is not a component. No stored column holds it.
The price return over one year and three years is computed in
`app/price_metrics.py` and is not part of this score.

The score reads the ratio columns. It does not divide net income by
equity itself. A row that stores revenue but leaves `roe` empty
contributes no profitability from that row. The ratios are
fractions: `0.15` means 15 percent. `debt_to_equity` is a percent,
the same unit Yahoo's `debtToEquity` uses and the same unit
`STOCK_METRICS` in `app/data_collectors/fake.py` stores. `45` means
0.45 times equity, not 45 times. `ter` is a fraction of assets per
year: `0.0022` means 0.22 percent. The collector's `profit_margin`
is stored on the score as `net_margin`. The legacy sample in
`app/core/init_db.py` stores ROE as `15.6` with a comment that means
15.6 percent. This score would treat `15.6` as far above the top of
the scale and clamp it to 100. Refs #136.

Volatility and max drawdown come from `metrics_from_bars` on the
default price series. That is the same series the instrument detail
route uses.

## The scale for one figure

Each usable figure is mapped onto 0–100 and then rounded half up to
two decimal places. A value past either end stays at 0 or 100.

For a straight line, `low` scores 0 and `high` scores 100:

```text
raw = (value - low) / (high - low) * 100
```

If `high` is smaller than `low`, a smaller value scores higher.
That is how "cheaper" and "calmer" work.

| Figure | 0 points | 100 points |
| --- | --- | --- |
| ROE | 0 | 0.20 (20 percent) |
| Net margin | 0 | 0.20 |
| P/E | 30 | 10 |
| P/B | 5 | 1 |
| Debt to equity (percent) | 200 | 0 |
| Current ratio | 0.5 | 2 |
| Revenue growth | -0.10 | 0.20 |
| TER | 0.01 (1 percent) | 0 |
| Volatility | 0.40 | 0.10 |
| Max drawdown | -0.50 | 0 |

Worked example. ROE `0.10` is halfway from 0 to 0.20, so 50. Net
margin `0.20` is the top, so 100. Profitability is the average, 75.
P/E 20 is halfway from 30 to 10, so 50. The same halfway reading
gives 50 for P/B 3, debt-to-equity 100 (1.0 times equity), current
ratio 1.25, and revenue growth 0.05. Debt-to-equity 45, the figure
stored for `DEMO_PL_TECH`, scores 77.50.

AUM uses a logarithm, because a fund ten times larger is the step
that matters, not a fixed amount of currency. `log10` of the AUM is
mapped from 7 to 11. 7 is 10 million and scores 0. 11 is 100 billion
and scores 100. 1 billion is `log10` 9, which is halfway, so 50.

Some stored numbers are not scored:

- P/E or P/B at or below 0. A negative multiple is not "cheap".
- Debt-to-equity below 0. That is negative equity, which this line
  does not describe. Zero debt scores 100.
- Current ratio below 0, TER below 0, or volatility below 0.
- AUM at or below 0.
- Max drawdown above 0. The price metric is 0 or negative.
- A boolean, a string, `NaN`, or an infinity.

A negative ROE, margin, or revenue growth is still a number. It
scores 0 when it is at or below the low end. It is not dropped.

## Freshness

The score date is today's date in UTC. Tests can replace that clock.
A figure is fresh when its date is on or after the score date minus
the window. The exact last day still counts. One day older does not.
A date in the future still counts. A missing date does not.

| Figure | Window |
| --- | --- |
| Stock ratios (`period_end`) | 548 days |
| TER and AUM | 366 days |
| Volatility and max drawdown | 92 days |

548 days is about eighteen months, so an annual filing can still be
the latest one. 366 days keeps a leap year inside one year for a
fee or a fund size. Volatility and max drawdown already describe a
year of weekly closes. A missed week does not make that year stale.
92 days is about one quarter, the same length the watchlist uses for
a trend window. The watchlist's 7-day rule is for the latest price,
not for this one-year figure. The day that is exactly 92 days back
is still fresh.

TER uses the attribute row's `as_of`. AUM uses `aum_as_of` when that
date is stored, and otherwise the row's `as_of`. A stock ratio uses
`period_end` converted to a UTC date. The price metrics use their
own as-of date, which is the last usable close.

For each stock column, the score keeps the newest row that has a
finite number in that column. A later quarterly row that leaves ROE
empty does not hide an older annual ROE. When two rows end at the
same instant, the annual row wins over the quarterly row.

A missing figure and a stale figure are both labelled `no data`.
The machine status is `no_data` or `stale`, so a later page can say
which one it was. The component is left out only when none of its
figures are usable. A component that was left out has status
`no_data`, label `no data`, and no contribution.

## Weights

The built-in set gives every component the weight `1`. Four weights
of 1 are equal shares. They are not stored as 0.25, because 1/4 is
exact when the code divides by the sum.

Version 1 is that built-in set. It is not a database row.
`stored` is false. The first PUT inserts version 2. Each later PUT
adds 1, even when the numbers did not change. Old versions are not
kept. The score is not saved either. The next GET computes it again
and reports the version it used.

A weight may be 0. That component is status `unused`. Its normalized
score is still shown, and it does not enter the total. It does not
count in the coverage numerator. A payload in which every weight is
0 is rejected.

Before the total is computed, the weights of the components that
enter it are divided by their sum. A missing component's weight is
not handed to anyone as a zero score. It is dropped, and the others
grow to fill 1. A weight of 0 is dropped the same way.

Example. Profitability is 75 and the other three components are 50,
with equal weights. The total is
`75/4 + 50/4 + 50/4 + 50/4 = 56.25`.
If growth has no figure, the remaining weights are 1, 1 and 1.
`75/3 + 50/3 + 50/3 = 58.333...`, which rounds to 58.33.

Changing profitability to weight 3, and leaving growth missing,
uses 3, 1 and 1. `75 * 3/5 + 50/5 + 50/5 = 65.00`.

## Rounding

Each input score and each component score is rounded half up to
two decimal places. Python's `round` uses half-to-even. This code
uses `Decimal` and `ROUND_HALF_UP`, which is the school rule: 0.005
rounds away from zero to 0.01.

The contribution starts as the renormalized weight times the
component score. The total is the sum of those values, rounded
half up to two decimal places. Each contribution is then cut down
to a whole cent, and the cents still needed to reach that total go
to the largest discarded fractions. A tie goes to the earlier
component. A contribution is never negative. Adding the published
contributions gives the published total.

`effective_weight` is the renormalized share rounded half up to
four decimal places. Multiplying that rounded share by the score
can be a hundredth away from the contribution. Add the
contributions, not the rounded shares.

Three components that each score 50, with equal weight, are
`16.67`, `16.67` and `16.66`. The total is `50.00`. Four equal
components that score `0.02`, `0.02`, `0.02` and `0.00` are
`0.01`, `0.01`, `0.00` and `0.00`. The total is `0.02`.

## Coverage and the oldest date

`coverage.label` is a short count such as `3 of 4`. `available` is
how many components entered the total. `total` is how many
components that instrument type has. A zero-weight component is
not in `available`.

`oldest_input_date` is the oldest date among the figures that were
actually used. A stale or missing figure does not set that date.
When nothing was used, the date is null.

On a component, `as_of` is the oldest used input of that component.
`source` is set when those inputs all name the same source.
Otherwise `source` is null. Each input still has its own source and
date.

## Where this shows up

`GET /api/v1/instruments/{id}/score` computes one score.
`GET` and `PUT /api/v1/score-weights/{instrument_type}` read and
replace the weight set. The shapes, status codes, and the fixed
error sentences are in `docs/api-demo.md`.

`DEMO_ETF_GPW` in `fixtures/demo-v2.json` has no TER. Cost is no
data. The 2025 annual row of each demo stock except `DEMO_PL_EMPTY`
stores the ratios from `STOCK_METRICS`, including debt-to-equity as
a percent and the collector's profit margin in `net_margin`.
`DEMO_PL_EMPTY` has no metric rows.

On 2026-11-18 the fixture prices still end on 2026-09-28, which is
51 days earlier. That is inside the 92-day window, and the 2025
annual ratios are inside the 548-day window. A score on that date
shows:

| Ticker | Status | Coverage |
| --- | --- | --- |
| `DEMO_PL_TECH` | scored | 4 of 4 |
| `DEMO_US_GROWTH` | scored | 4 of 4 |
| `DEMO_DE_INDUSTRY` | scored | 4 of 4 |
| `DEMO_JP_STABLE` | scored | 4 of 4 |
| `DEMO_SG_EARLY` | scored | 3 of 4 |
| `DEMO_PL_EMPTY` | no_score | 0 of 4 |
| `DEMO_ETF_WORLD` | scored | 4 of 4 |
| `DEMO_ETF_GPW` | scored | 3 of 4 |
| `DEMO_ETC_GOLD` | scored | 4 of 4 |
| `DEMO_ETC_SILVER` | scored | 4 of 4 |

`DEMO_SG_EARLY` has no P/E and no revenue growth, so growth is no
data and valuation uses P/B alone. 2026-12-29 is still inside the
window (92 days after 2026-09-28). 2026-12-30 is the first stale
day. Until the fixture gains a later close, a score on or after
that date drops volatility and max drawdown.
