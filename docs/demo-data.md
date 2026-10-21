# Reusable Synthetic Demo Data

> Commands using `$TMPDIR/investment-demo-fixtures` refer to the original
> temporary checkout. Substitute your current checkout containing this file.
> Provision a local API with the [IDE startup guide](ide-startup.md) first;
> the old demo runtime is not guaranteed to survive cleanup.

The versioned sources are [demo-v1.json](../fixtures/demo-v1.json) and
[demo-v2.json](../fixtures/demo-v2.json), not a download of real
securities or financial statements. All names, tickers, exchanges, and
amounts are invented. No data-provider keys or investment decisions are involved.
These fixtures are for API and UI testing; they are not a real portfolio.
`demo-v1` is the older company-and-metrics file. `python -m scripts.run_demo`
seeds `demo-v2`. `python -m scripts.seed_demo --fixture demo-v1` still
seeds the older file.

## One command

From the repository root, with the runtime requirements installed and
no `.env` file:

```bash
python -m scripts.run_demo
```

That creates a fresh SQLite file at `demo/investment_demo.db`
(git-ignored), seeds the `demo-v2` fixture (stocks, ETFs, ETCs, and
weekly prices), selects the fake collector, and serves
[http://127.0.0.1:8000/ui](http://127.0.0.1:8000/ui).
The host is `127.0.0.1`. The command does not read `DATABASE_URL` from
`.env` or from the shell, and it refuses any database that is not that
SQLite file, including a `demo/` directory that is a symlink. It always
generates a fresh `SECRET_KEY` for the process, even when the shell
already has one. The key is not printed and it is not written to disk.
If the port is already in use, the command stops and leaves the
database file unchanged.

Run the command again to replace the file and seed from scratch.
`--reset` is that same default, written out. `--keep` reuses the file
and only inserts fixture rows that are missing, so a second run does
not duplicate them. `--reset` and `--keep` cannot be combined.

```bash
python -m scripts.run_demo --keep
python -m scripts.run_demo --port 8000
```

## Local /ui demo

The one command above is the short path. The steps in
[Run the demo](RUN_DEMO.md) are the same pieces, run by hand. The
server-rendered pages are at `/ui`. The seeder opens only the sqlite
URL you pass. It does not read or change the default `DATABASE_URL`.

`SECRET_KEY` is required for the seed and for uvicorn. Generate it
with the command in that guide. Do not commit it. The documented
bind is `127.0.0.1`. `python main.py` binds `127.0.0.1` as well.
`ALLOWED_HOSTS` defaults to `localhost,127.0.0.1`.

Those commands created 6 companies and 20 metric rows. `GET /ui`,
`GET /ui/instruments/1`, the CSS, and the local HTMX file each
returned 200. `demo/` is gitignored.

- Polish is the default. The EN link stores `ui_lang` and comes back
  to the same `/ui` path.
- Rows from this fixture show the synthetic-data badge. The current
  `/ui` pages still show the older disclaimer banner. Product
  requirements v0.4 no longer require that notice.
- A description that starts with `[IAC-DEMO-` gets that badge,
  including one a person types by hand. The label can be
  misleading. It is not a bypass of the seeder, and it is
  acceptable for this local demo. The source is `demo-` plus the
  token up to the next `]`, in lowercase, when that token is 1
  to 16 ASCII letters or digits. `[IAC-DEMO-V2]` shows
  `demo-v2`. Anything else shows `demo`.
- A website is a link only when the view-model accepts `http` or
  `https`. Anything else is plain text. An empty website is
  "brak danych" / "no data".

## Offline collector

`DATA_COLLECTOR=fake` makes `POST /api/v1/data-collection/fetch-company`
use the offline `FakeCollector` instead of Yahoo Finance. It serves the
stock profiles from this fixture plus the funds `DEMO_ETF_WORLD` and
`DEMO_ETC_GOLD`, all with the `[IAC-DEMO-V1]` marker. An unknown ticker
returns 404. `DEMO_PL_EMPTY` has a profile, so fetch-company creates it
(200); only its key metrics and price history are "no data" (`None`).
The default is `yahoo`. The test suite sets `fake` itself, in every
pytest selection mode, so a shell value cannot turn tests online.

## Scenarios

| Ticker | Country / currency | Scenario |
| --- | --- | --- |
| `DEMO_PL_TECH` | Poland / PLN | Profitable software company with growing revenue |
| `DEMO_US_GROWTH` | USA / USD | Losses followed by a profitable quarter |
| `DEMO_DE_INDUSTRY` | Germany / EUR | Declining sales, then a loss-making quarter |
| `DEMO_JP_STABLE` | Japan / JPY | Stable positive earnings and larger nominal values |
| `DEMO_SG_EARLY` | Singapore / SGD | Zero revenue, losses, missing fields and website |
| `DEMO_PL_EMPTY` | Poland / PLN | No financial reports; missing website and sector |

The first five companies each have annual records for 2023, 2024, and 2025, plus
one quarterly record ending March 31, 2026: **six companies and 20 metric rows**.
The sixth company deliberately has no metrics. Annual and quarterly records
should not be compared as equal-length periods. Monetary figures use each
company's currency, not a common currency; there is no FX conversion. Optional
ratios not supplied by this fixture remain null, not zero. The v1
file does not set `instrument_type`. A company created from it is
stored as `STOCK`.

## demo-v2

[demo-v2.json](../fixtures/demo-v2.json) is what `python -m scripts.run_demo`
loads. The marker is `[IAC-DEMO-V2]`, on every company description and
on every price `source`. The six v1 companies are stocks. Two synthetic
ETFs (`DEMO_ETF_WORLD`, `DEMO_ETF_GPW`) and two synthetic ETCs
(`DEMO_ETC_GOLD`, `DEMO_ETC_SILVER`) are added. ETF and ETC attribute
columns (TER, issuer, and the rest) are issue #28 and are not in this
file.

Prices are weekly session dates (Mondays) from 2022-10-03 through
2026-09-28, in the instrument's own currency. There is no FX
conversion. `DEMO_PL_EMPTY` has no price bars, which is the missing
series. `DEMO_JP_STABLE` stops on 2024-09-30 and its `retrieved_at`
is that day, so the series is stale against the fixture `as_of` of
2026-09-30. A missing open, high, low, close, or volume is null, not
zero. The numbers are a closed-form curve, not a market.

`GET /api/v1/instruments/{id}/prices?from=&to=` reads the stored bars.
`from` and `to` are inclusive. One session can be stored under two
sources, for example the fixture marker and a later `fake` refresh.
When `source` is omitted, the list is still one series. That source
is chosen from every bar of the instrument, not from the date window:
the bar with the latest `retrieved_at` wins, and if two sources share
that time the source name that sorts last is kept, so `fake` wins a
tie with `[IAC-DEMO-V2]`. The `from` and `to` filters run after that
choice. A window that only contains the other source returns `[]`.
After a refresh the default source is `fake`, because those bars were
retrieved later. Pass `source=[IAC-DEMO-V2]` to get the demo series.
The seeder asks for that source, so a newer refresh does not hide the
fixture rows it skips.

Each OHLC value in that JSON is a string with 8 digits after the
decimal point, for example `"119.64060000"`, not a JSON number.
The columns are `Numeric(20, 8)`. FastAPI serializes `Decimal` as a
string; the model uses fixed-point so a tiny price is not written as
`1E-8`. A JSON number or a numeric string is accepted on input, and
extra digits are rounded half-even to 8 places. Volume stays a JSON
integer. The string `"100"` is rejected. PostgreSQL stores the
decimal exactly. SQLite declares the same numeric type, and its
numeric affinity keeps the value as a real, so a price with more
significant digits than a binary float can hold is exact on
PostgreSQL only.

`POST /api/v1/instruments/{id}/prices/refresh`
upserts bars from the configured collector. With `DATA_COLLECTOR=fake`
a second refresh does not insert a second copy of the same session.
The currency on a refreshed bar is the currency stored on the
instrument, because a collector bar has no currency of its own. The
source and the retrieval time come from the collector's provenance.

The `/ui` synthetic badge matches a description that starts with
`[IAC-DEMO-`, so a demo-v2 row shows it. `[IAC-DEMO-V1]` is not a
separate check. The token rule is in the section above.

Seed demo-v2 without the one-command demo:

```bash
python -m scripts.seed_demo --database-url "sqlite:///demo/investment_demo.db" --fixture demo-v2 --apply
```

A second `--apply` skips companies, metrics, and prices that are
already stored. It does not update them. The price skip key is the
instrument, the session date, and the source.

## Preview And Apply

The existing demo API is at `http://127.0.0.1:8081`. Its running application stays
in `$TMPDIR/investment-api-demo`; the newer fixture tooling is in a separate
worktree so no application restart or production-code change is required.

```bash
cd $TMPDIR/investment-demo-fixtures
PYTHON=~/IdeaProjects/Investment-AI-Companion/.venv/bin/python

# Read-only preview; no POST, PUT, or DELETE.
"$PYTHON" -m scripts.seed_demo --base-url http://127.0.0.1:8081

# Explicitly add missing fixture records to this isolated demo.
"$PYTHON" -m scripts.seed_demo --base-url http://127.0.0.1:8081 --apply
```

Confirm the URL points at the isolated demo before applying. The client only
accepts numeric loopback addresses and disables proxies/redirects, but loopback
alone cannot prove that the server uses a disposable database. Never aim it at
an API backed by valuable data. Do not use `setup_database.py --seed` for this
fixture: that legacy seed uses a different dataset and skips nonempty databases.

## Repeatability And Preservation

- The client creates only missing records; it never updates or deletes records.
- Companies match by reserved ticker. Existing fixture companies must retain
  the description prefix of the fixture being applied (`[IAC-DEMO-V1]` or
  `[IAC-DEMO-V2]`); otherwise the client reports a collision before writing.
  This avoids attaching fixture metrics to unrelated companies using the
  same ticker. Leave that prefix when editing descriptions.
- demo-v2 prices match by instrument, session date, and source. A price
  whose source is not `[IAC-DEMO-V2]` is not a fixture row and is left
  in place.
- Existing company fields and metric values are preserved. Financial rows
  match by company, period type, and UTC-equivalent period-end timestamp.
- A second run fills only missing fixture rows; it does not restore edited
  values. Deliberately deleted fixture rows will be recreated on the next apply.
- Existing unrelated records, including the original `DEMO` company and your
  manually created records, are not touched.
- Each POST commits separately. A failed run can leave a partial seed; fix the
  reported issue and rerun to add missing items. No automatic rollback or
  destructive reset is provided. Run one seeder at a time.

## Inspect Through API Or Swagger

Open [Swagger](http://127.0.0.1:8081/docs) and use company and financial-metrics
GET endpoints. IDs are assigned by the database; do not assume fixed IDs or
that the fixture is the only data in the database.

```bash
BASE_URL=http://127.0.0.1:8081
curl -q --noproxy '*' -fsS "$BASE_URL/api/v1/companies/?skip=0&limit=100"

# Substitute an ID returned by the list, not the ticker.
COMPANY_ID=1
curl -q --noproxy '*' -fsS "$BASE_URL/api/v1/companies/$COMPANY_ID"
curl -q --noproxy '*' -fsS \
  "$BASE_URL/api/v1/financial-metrics/company/$COMPANY_ID?skip=0&limit=100"
```

For create/update/delete request examples and the isolated runtime's lifecycle,
see [the API demo guide](api-demo.md). The `/ui` list and detail pages
are in [Run the demo](RUN_DEMO.md). The server filters the seeded
companies. The browser sends the form and swaps in the HTML fragment.

## Old SQLite demo databases

Recreate an old SQLite demo database. Do not keep using that file.
Rows written with a non-UTC offset are read back 2h off, and nothing
migrates them. Create a fresh file and run `--apply` again.

## Storage And Recovery

The JSON fixture and scripts are committed in Git. The running PostgreSQL
database remains under `$TMPDIR/iac-demo.h7TbGw/data`, which can be removed
by system cleanup. This is deliberately disposable storage, not a backup.
After provisioning a fresh isolated demo with empty tables, apply the committed
fixture again. User edits are not in the fixture and must be backed up separately
if valuable. No runtime reset or database deletion is performed by the seeder.
