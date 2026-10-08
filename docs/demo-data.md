# Reusable Synthetic Demo Data

> Commands using `$TMPDIR/investment-demo-fixtures` refer to the original
> temporary checkout. Substitute your current checkout containing this file.
> Provision a local API with the [IDE startup guide](ide-startup.md) first;
> the old demo runtime is not guaranteed to survive cleanup.

The versioned source is [demo-v1.json](../fixtures/demo-v1.json), not a download
of real securities or financial statements. All names, tickers, exchanges, and
amounts are invented. No data-provider keys or investment decisions are involved.
This fixture is for API and UI testing; it is not a real portfolio.

## Local /ui demo

The server-rendered pages are at `/ui`. They read a sqlite file. Seed that
file first, then start uvicorn against the same URL. The seeder opens only
the URL you pass. It does not read or change the personal `DATABASE_URL`.

From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
python -m scripts.seed_demo --database-url "sqlite:///demo/investment_demo.db" --apply
DATABASE_URL="sqlite:///demo/investment_demo.db" python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/ui](http://127.0.0.1:8000/ui).

These commands were run from a clean virtualenv installed only from
`requirements.lock` (jinja2 3.1.6). The seed created 6 companies and 20
metric rows. `GET /ui`, `GET /ui/instruments/1`, the CSS, and the local
HTMX file each returned 200. `demo/` is gitignored.

- Bind `127.0.0.1` only. Do not start the demo with `python main.py`:
  that entry point still binds `0.0.0.0`.
- Polish is the default. The EN link stores `ui_lang` and comes back
  to the same `/ui` path.
- Rows from this fixture show the synthetic-data badge. The page
  disclaimer stays visible. The output is research context, not a
  recommendation.
- A website is a link only when the view-model accepts `http` or
  `https`. Anything else is plain text. An empty website is
  "brak danych" / "no data".
- After PR #61 merges, the demo command also needs `SECRET_KEY`
  (at least 32 characters, not a placeholder). One way to make one:
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
  That pull request also checks `Host`. `127.0.0.1` and `localhost`
  are allowed by default, which matches `--host 127.0.0.1`.
  Whichever of #61 and #63 lands second updates this file.
  On current master the commands above are enough.

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
ratios not supplied by this fixture remain null, not zero. This app currently
models companies, not separate bond/ETF/ETC instrument types.

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
  the description prefix `[IAC-DEMO-V1]`; otherwise the client reports a
  collision before writing. This avoids attaching fixture metrics to unrelated
  companies using the same ticker. Leave that prefix when editing descriptions.
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
see [the API demo guide](api-demo.md). The `/ui` list and detail pages are
documented above. They filter the seeded companies in the browser.

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
