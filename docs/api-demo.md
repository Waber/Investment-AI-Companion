# Local API Demo

This is the existing FastAPI backend, not a frontend. AI analysis and investor
profiles are not implemented. All company names, tickers, and financial values
below are synthetic, not market data or investment advice. Example website URLs
are stored as strings; CRUD requests do not visit them.

Runtime data is under `/private/tmp` and may disappear after system cleanup or
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
export PYTHON=/Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python
curl -q --noproxy '*' -fsS "$BASE_URL/"
"$PYTHON" /private/tmp/investment-api-demo/scripts/smoke_demo.py --base-url "$BASE_URL"
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
uses an external Yahoo Finance network call, and can create or update a company.
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

```bash
export DEMO_DIR=/private/tmp/iac-demo.h7TbGw
export PG_BIN=/opt/homebrew/opt/postgresql@14/bin
export REPO=/private/tmp/investment-api-demo
export PYTHON=/Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python
export DATABASE_URL='postgresql://demo@/investment_demo?host=/private/tmp/iac-demo.h7TbGw&port=15432'
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
