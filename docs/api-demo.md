# Local API Demo

> Historical runtime: the absolute `$TMPDIR` paths below describe the
> September 26 session and may no longer exist. They are not a current health
> check or a fresh-install procedure. For a new local run, start with the
> [IDE startup guide](ide-startup.md).

This is the existing FastAPI backend, not a frontend. AI analysis and investor
profiles are not implemented. All company names, tickers, and financial values
below are synthetic, not market data or investment advice. Example website URLs
are stored as strings; CRUD requests do not visit them.

Runtime data is under `$TMPDIR` and may disappear after system cleanup or
reboot. Do not store valuable data here. The seeded `DEMO` company and its
metrics are synthetic. Swagger loads UI assets from a CDN; curl does not need
those assets. Commands below disable curl configuration and proxy inheritance.

There is no authentication. Keep HTTP bound to loopback; do not expose this demo
through a public interface or tunnel. Use only the isolated demo database, never
the developer database or repository `.env`.

For a repeatable dataset of six synthetic companies and 20 financial records,
see [Reusable Synthetic Demo Data](demo-data.md). It includes missing-data and
loss-making scenarios and preserves existing records on repeated application.

## Open And Check

After the coordinator confirms the demo is ready:

```bash
export BASE_URL=http://127.0.0.1:8081
export PYTHON=~/IdeaProjects/Investment-AI-Companion/.venv/bin/python
curl -q --noproxy '*' -fsS "$BASE_URL/"
"$PYTHON" $TMPDIR/investment-api-demo/scripts/smoke_demo.py --base-url "$BASE_URL"
```

- [Swagger UI](http://127.0.0.1:8081/docs)
- [ReDoc](http://127.0.0.1:8081/redoc)
- [OpenAPI JSON](http://127.0.0.1:8081/api/v1/openapi.json)

The stdlib smoke script requires an explicit loopback IP/port, disables proxies
and redirects, creates unique records, checks reads/updates/422/404, and attempts
cleanup of only its own returned IDs in `finally`. Failures, including cleanup
failures, exit nonzero. Loopback validation cannot verify which database an API
uses: confirm this demo process first. If a POST commits but its response is lost,
the script cannot recover the unknown ID; inspect the isolated demo manually.

## Example Requests

Run these blocks in order in the same bash/zsh session. Collection POST URLs have
a trailing slash. Successful POST/GET/PUT/DELETE return 201/200/200/204 respectively.
IDs are captured from responses using Python, not hardcoded or parsed with jq.

```bash
TICKER="DEMO$("$PYTHON" -c 'import uuid; print(uuid.uuid4().hex[:16].upper())')"
COMPANY_JSON=$(curl -q --noproxy '*' -fsS -X POST "$BASE_URL/api/v1/companies/" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"Synthetic $TICKER\",\"ticker\":\"$TICKER\",\"website\":\"https://example.com/\",\"currency\":\"USD\"}")
COMPANY_ID=$(printf '%s' "$COMPANY_JSON" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["id"])')
curl -q --noproxy '*' -fsS "$BASE_URL/api/v1/companies/?skip=0&limit=100"
curl -q --noproxy '*' -fsS "$BASE_URL/api/v1/companies/$COMPANY_ID"
curl -q --noproxy '*' -fsS -X PUT "$BASE_URL/api/v1/companies/$COMPANY_ID" \
  -H 'Content-Type: application/json' -d '{"website":"https://example.org/"}'
curl -q --noproxy '*' -fsS -X PUT "$BASE_URL/api/v1/companies/$COMPANY_ID" \
  -H 'Content-Type: application/json' -d '{"website":null}'
```

PUT updates only supplied fields. Omitting `website` preserves it; explicit
`null` clears it. URLs must be valid HTTP(S) URLs and can be normalized on return.
Currency is stored in uppercase (`usd` becomes `USD`). Yahoo's
minor-unit codes `GBp` (pence) and `ZAc` (South African cents) are kept
exactly as sent: rewriting `GBp` to `GBP` would treat the amount as
pounds.

Price fields on a bar (`open`, `high`, `low`, `close`) are decimal
strings such as `10.50000000`, not JSON numbers. Parse them with
`Decimal` or another decimal library. Never use float math: a binary
float cannot hold every 8-place price.

`POST /api/v1/instruments/{id}/prices/refresh` upserts the collector's
bars. `bar_count` is the number of stored keys (the session date and
the source), not the number of bars the collector returned. Two bars
in one refresh with the same date and source count once: the later
bar is stored and the response is 200. Prices that differ do not turn
that refresh into 400. A discarded earlier copy is not validated, so
a bad currency on that copy does not reject the batch when the last
copy is valid.

`instrument_type` is `STOCK`, `ETF`, or `ETC`. Omitting it on create
stores `STOCK`. On update, omit it to keep the stored type. JSON
`null` is 422. A value already stored outside those three is returned
as `null` on read, so one bad row does not fail `GET /companies/`.
`isin` is an uppercase ISO 6166 identifier, or `null`. Sending
`null` on update clears it. A name that is empty after stripping
spaces is 422. Surrounding spaces are removed before the name is
stored.

Company `name` and watchlist `label` share one text checker. A value
that is only too long stays Pydantic `string_too_long`: company
`ctx.max_length` is 255 and the message is `String should have at
most 255 characters`; a watchlist label uses 80 and the same
sentence. The other text failures are `value_error`. `ctx.error` is
`{code, field}` (`code` is `blank`, `control_char`, `bidi`, or
`surrogate`). It used to be `{}`. `type` and `msg` are unchanged in
shape. A blank company name still says `Value error, name must
contain a visible character`. A value made only of combining marks
(`Mn`, `Mc`, `Me`, for example U+0301) is blank. A company name
made only of those marks is 422 with the blank message above. A
marks-only watchlist label becomes JSON `null`, the same as a
blank label. A marks-only note body, thesis title, or thesis body
is now 422 `blank`; those fields used to store the marks.
Thesis-breakers allow a blank, so marks-only breakers become `""`.
A letter keeps its mark.

What differs from the previous write rules:

- A trailing newline on a company name, a watchlist label, or a
  thesis title is 422 `control_char`. It used to be stripped and the
  rest stored (`ETF\n` became `ETF`). NEL (U+0085) is rejected even
  when newlines are allowed. `str.splitlines` treats NEL as a line
  break, so a note that contained one could forge a second log line.
  Master stripped a NEL at the edge as whitespace.
- A company name that is only U+202E was already 422. A bidi or
  hidden-format mark beside a letter is now 422 `bidi`. A surrogate
  beside a letter used to make the error encoder raise
  `UnicodeEncodeError`, so the client saw 500, not 201. It is now
  422 `surrogate`, and `input` shows the ASCII `\u` escape.
- The `/ui` company name calls `clean_text`. `blank` shows
  `error.required`, `too_long` shows `error.too_long`, and
  `control_char`, `bidi`, and `surrogate` show `error.invalid`.
  The HTTP API still reports a too-long name as `string_too_long`.
- Note bodies, thesis bodies, and thesis-breakers now reject bidi
  marks and tag characters. On master only the title did.
- A watchlist label made only of private-use (Co) or unassigned (Cn)
  characters is stored as JSON `null`, the same as a blank label. It
  is not a 422, so it has no `type` or `ctx.error.code`. It used to
  be stored as that text. The same Co/Cn-only value is now blank for
  a note or a thesis (422 on a required field, `""` for
  thesis-breakers). There is no HTTP route for notes or theses yet.
- The watchlist bidi message is `Value error, label must not contain
  hidden or bidi controls`. It used to say `hidden format controls`.
  A thesis title used to say `bidi controls` and now says
  `hidden or bidi controls`.
- A thesis title keeps a format character at either edge. U+2028 at
  an edge is stripped; one in the middle is kept. A line or paragraph
  separator used to be 422 anywhere in the title.
- Tag characters U+E0000–U+E007F are `bidi`. That range also rejects
  the England, Scotland, and Wales subdivision flags, which are the
  black flag plus those tags.
- `POST /api/v1/data-collection/fetch-company` strips edge whitespace
  from a provider name before validation, including spaces, tabs, CR,
  and LF. A padded name is stored. A provider name that contains LRM
  or another bidi or tag character still fails, and the fetch
  returns 502.
- The 422 handler sets `ctx.error` to `{code, field}` for a text
  error and to `{}` for any other exception. An extra attribute on
  the exception is not copied into the body.

An existing database does not gain these columns by itself. Startup
creates missing tables and then refuses to serve when `companies`
exists without `instrument_type` or `isin`. An Alembic-managed
database runs `alembic upgrade head` (revision `0001` for these
columns, the `ck_companies_instrument_type` CHECK, and the
`uq_companies_isin` unique index, revision `0002` for `price_bars`,
then revision `0003` for the `uq_companies_ticker` unique index,
then the later revisions). `alembic heads` shows the current head,
so this note does not name a revision the next migration would make
stale. `0003` stops when stored tickers collide after trim
and uppercase. The trim removes spaces, tabs, carriage returns, and
line feeds, so `aapl` and `AAPL ` are one collision. It names that
stored text and does not rewrite the rows. On SQLite the index is
created in place, so `price_bars` rows stay. Revision `0007` replaces
that index with a unique index on `upper(ticker)`. It stops when
`upper(ticker)` collides (`aapl` and `AAPL`) and does not rewrite
those rows. It drops `uq_company_name_ticker` when that constraint is
present. On SQLite the drop copies only `companies`, with foreign keys
off for the copy, so child rows stay.
The index expression is `upper(ticker)` with no trim, so raw SQL
can store both `AAPL` and `AAPL ` (a trailing space). The API
strips and uppercases a ticker before it writes, so a request
cannot store that pair. The command's preflight still trims
spaces, tabs, carriage returns, and line feeds, and it will
report `AAPL` and `AAPL ` as one collision. The index does not
use `trim()` because SQLite's one-argument `trim` and
PostgreSQL's `trim` both remove spaces only, while a two-argument
trim is `TRIM` on SQLite and `BTRIM` on PostgreSQL. One index
expression has to mean the same thing on both, so it is
`upper(ticker)` only.
A database created by an older
startup `create_all` needs that upgrade. Adding the columns by hand
skips the CHECK, the `uq_companies_isin` unique index, and
`alembic stamp head`. A fresh `create_all` database already has the
columns: run `alembic stamp head`, not `alembic upgrade head`.

The same company name may be stored on two tickers, on create and on
update. `BRK.A` and `BRK.B` can both be named Berkshire Hathaway.
A duplicate ticker or ISIN is 400. `detail` stays a plain string.
`code` is an extra field for form mapping (`duplicate_ticker` or
`duplicate_isin`). Create and update use the same sentence. The
repository raises `app.repositories.company_errors.DuplicateTickerError`
or `DuplicateIsinError`. Both subclass `DuplicateCompanyError`, which
subclasses `ValueError`, and each class has a `code` attribute.

```json
{"detail": "A company with this ticker already exists", "code": "duplicate_ticker"}
```

```json
{"detail": "A company with this ISIN already exists", "code": "duplicate_isin"}
```

```bash
METRICS_JSON=$(curl -q --noproxy '*' -fsS -X POST "$BASE_URL/api/v1/financial-metrics/" \
  -H 'Content-Type: application/json' \
  -d "{\"company_id\":$COMPANY_ID,\"period_end\":\"2025-12-31T00:00:00Z\",\"period_type\":\"annual\",\"revenue\":1000000,\"net_income\":100000}")
METRICS_ID=$(printf '%s' "$METRICS_JSON" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["id"])')
curl -q --noproxy '*' -fsS "$BASE_URL/api/v1/financial-metrics/$METRICS_ID"
curl -q --noproxy '*' -fsS -X PUT "$BASE_URL/api/v1/financial-metrics/$METRICS_ID" \
  -H 'Content-Type: application/json' -d '{"revenue":1100000}'
curl -q --noproxy '*' -fsS "$BASE_URL/api/v1/financial-metrics/company/$COMPANY_ID"
```

Metrics `PUT` accepts `period_end` and stores that instant as UTC.
Omitting `period_end` leaves the stored value unchanged. An explicit
`null` is rejected with 422. Company `website` is different: the
example above sends `{"website": null}` and that clears the website.

Invalid URL: expected 422, without changing the company. Deliberate error examples
omit curl's `-f` so the response body and status remain visible.

```bash
curl -q --noproxy '*' -sS -i -X PUT "$BASE_URL/api/v1/companies/$COMPANY_ID" \
  -H 'Content-Type: application/json' -d '{"website":"not-a-url"}'
```

Clean up only the IDs created above, metrics before company. Do not substitute an
existing record's ID. Stop and inspect any failed creation before continuing.
Company deletion also cascades to its metrics. After deletion, PUT to those same
IDs must return 404:

```bash
curl -q --noproxy '*' -fsS -i -X DELETE "$BASE_URL/api/v1/financial-metrics/$METRICS_ID"
curl -q --noproxy '*' -fsS -i -X DELETE "$BASE_URL/api/v1/companies/$COMPANY_ID"
curl -q --noproxy '*' -sS -i -X PUT "$BASE_URL/api/v1/companies/$COMPANY_ID" \
  -H 'Content-Type: application/json' -d '{"name":"Still synthetic"}'
curl -q --noproxy '*' -sS -i -X PUT "$BASE_URL/api/v1/financial-metrics/$METRICS_ID" \
  -H 'Content-Type: application/json' -d '{"revenue":1}'
```

Unexpected company/metrics write errors return generic 500 responses. Some
database constraint failures can also surface as 500, not always 400. Inspect
the local API logs rather than assuming a 500 proves nothing was written.

## External Collection Is Not Part Of This Demo

`POST /api/v1/data-collection/fetch-company` with `{"ticker":"AAPL"}` is optional,
uses an external Yahoo Finance network call (with `DATA_COLLECTOR=yahoo`, the
default), and can create or update a company. With `DATA_COLLECTOR=fake` it uses
the offline synthetic collector instead (see [Demo data](demo-data.md)).
It is **UNVERIFIED and was not run** for this demo; do not include it in smoke
tests. It is not covered by the synthetic-record cleanup above.

`POST /api/v1/data-collection/fetch-financial-metrics` accepts the same body but
is only a placeholder: HTTP 200 reports that it is not implemented, not that real
financial data was fetched. Neither collection route uses a trailing slash.

## Stop And Restart The Isolated Runtime

The coordinator provisions PostgreSQL 14.19, role `demo`, database
`investment_demo`. Existing startup runs `Base.metadata.create_all`; this demo
does not add or run migrations. These commands reuse the existing cluster only.
Do not run `initdb`, drop databases, or delete the runtime directory.
This block is historical. Substitute your own `$TMPDIR` path; do not reuse
another machine's temporary directory.

```bash
export DEMO_DIR=$TMPDIR/iac-demo.h7TbGw
export PG_BIN=/opt/homebrew/opt/postgresql@14/bin
export REPO=$TMPDIR/investment-api-demo
export PYTHON=~/IdeaProjects/Investment-AI-Companion/.venv/bin/python
# Double quotes so $TMPDIR expands. Single quotes would leave it literal.
export DATABASE_URL="postgresql://demo@/investment_demo?host=$TMPDIR/iac-demo.h7TbGw&port=15432"
```

Stop the foreground API with Ctrl-C. For the coordinator-started API, inspect the
PID from its runfile first; a stale PID may belong to another process. Only send
TERM after confirming it is this demo's Uvicorn process:

```bash
API_PID=$(cat "$DEMO_DIR/api.pid")
ps -p "$API_PID" -o pid=,command=
# After confirming the process identity:
kill -TERM "$API_PID"
"$PG_BIN/pg_ctl" -D "$DEMO_DIR/data" -m fast -w stop
```

Restart PostgreSQL only when stopped (the options keep it socket-only), then
start Uvicorn in the foreground from the runtime directory. It must not contain
a `.env`; the clean environment and different working directory prevent loading
developer configuration. No real API keys are required for CRUD.

```bash
"$PG_BIN/pg_ctl" -D "$DEMO_DIR/data" status
# Only if stopped:
"$PG_BIN/pg_ctl" -D "$DEMO_DIR/data" -l "$DEMO_DIR/postgres.log" \
  -o "-k $DEMO_DIR -p 15432 -h ''" -w start
cd "$DEMO_DIR"
test ! -e .env && /usr/bin/env -i PATH=/usr/bin:/bin \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$REPO" DATABASE_URL="$DATABASE_URL" \
  DEBUG=False BACKEND_CORS_ORIGINS='[]' OPENAI_API_KEY= \
  SECRET_KEY="$("$PYTHON" -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  "$PYTHON" -m uvicorn main:app --host 127.0.0.1 --port 8081
```

Use Ctrl-C for this foreground restart; the old `api.pid` is not refreshed by
these commands. Check CRUD with the smoke script in a second terminal: the root
response alone is not a database health check because startup logs database
errors without necessarily stopping the API. Stop/start preserves database files.
