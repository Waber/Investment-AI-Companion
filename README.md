# Investment AI Companion

Investment AI Companion is a FastAPI service for investment research workflows. It stores company data, financial metrics, and market-data collection results that can support analysis and decision hygiene.

Analysis, scores and signals show sources, data freshness, assumptions, risks and uncertainty. The product does not require a notice that output is not investment advice (decision 2026-10-10, `docs/product-requirements.md` section 12). Buy and sell signals, real portfolios and the later AI Portfolio are specified there and are not in the current demo.

To run the local `/ui` demo, follow [Run the demo](docs/RUN_DEMO.md).

## Current Scope

- FastAPI backend with API routes under `/api/v1`.
- SQLAlchemy persistence for companies and financial metrics.
- Yahoo Finance data collection code for market-data ingestion.
- Repository-level guidance in `AGENTS.md` and forward-looking delivery notes in `docs/development-journal.md`.
- Baseline API tests in `tests/`, run from the repository root. The command in Tests And Quality Checks prints a coverage report and treats `DeprecationWarning` as an error.

## Planned Or Configured Integrations

The environment template includes configuration keys for Redis, Elasticsearch, OpenAI, news, and social-media providers. Treat these as planned or configured integrations unless the corresponding application code exists and is covered by tests. The Redis, Elasticsearch, and OpenAI client libraries are not installed. The settings keys remain. The planned AI provider is Gemini through `google-genai`, and that package is not pinned yet.

## Project Structure

```text
investment_ai_companion/
├── app/
│   ├── api/                 # API endpoints, mounted under /api/v1
│   ├── core/                # Configuration, database, and startup helpers
│   ├── data_collectors/     # Market-data collection modules
│   ├── models/              # Pydantic and SQLAlchemy models
│   └── repositories/        # Persistence access helpers
├── docs/                    # Project documentation and delivery journal
├── tests/                   # Automated tests for API and behavior coverage
├── main.py                  # FastAPI application entrypoint
├── requirements.txt         # Direct runtime dependencies
├── requirements-dev.txt     # Runtime set plus test and lint tools
├── requirements.lock        # Hashed runtime lock
├── requirements-dev.lock    # Hashed dev lock; CI installs this
└── setup_database.py        # Local database setup helper
```

## Requirements

- Python 3.12 is the minimum. The locked numpy 2.5.3 requires
  Python >=3.12.
- PostgreSQL for the default application database.
- A local virtual environment at `.venv`, created on each machine
  (it is not committed or copied). Python 3.14 does not install the
  locks yet; see [#73](https://github.com/Waber/Investment-AI-Companion/issues/73).
- Redis, Elasticsearch, OpenAI, news, and social-media credentials only when working on features that use them.

## Setup

For step-by-step IDE configuration (PyCharm, IntelliJ IDEA, Cursor), see [Run and debug in an IDE](docs/ide-startup.md).
The application currently has a backend and Swagger UI, not a separate frontend.

1. Create and activate the virtual environment with Python 3.12.
   Name the version: plain `python3` can be a newer Python (Homebrew
   installs 3.14), and plain `python` may not exist on macOS.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python --version   # Python 3.12.x
```

2. Install dependencies from the hashed lock. Use the dev lock for
   tests and lint. Use the runtime lock when you only need the API.

```bash
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
```

```bash
.venv/bin/python -m pip install --require-hashes -r requirements.lock
```

`requirements.txt` and `requirements-dev.txt` are the direct pins.
The lock files are the exact set, with hashes. Regenerate them on
Python 3.12 after you change a pin. Pass `--strip-extras` so the
lock does not keep extras markers such as `coverage[toml]`. The
dev command also passes `--allow-unsafe` because pip-tools depends
on setuptools, and `--require-hashes` rejects an unpinned setuptools.

```bash
python -m piptools compile --generate-hashes --strip-extras --output-file=requirements.lock requirements.txt
python -m piptools compile --allow-unsafe --generate-hashes --output-file=requirements-dev.lock --strip-extras requirements-dev.txt
```

These locks were generated for Python 3.12 on Linux and macOS, and
they have no environment markers. A hashed install fails on Windows
(tzdata, colorama) and on Python older than 3.11. Use Python 3.12
on macOS or Linux. Universal locks are follow-up
[#53](https://github.com/Waber/Investment-AI-Companion/issues/53).

3. Create local environment configuration:

```bash
cp .env.example .env
```

Edit `.env` for local credentials and service URLs. Do not commit real secrets.

`SECRET_KEY` is required and must be at least 32 characters. The process
refuses to start when it is missing, shorter than that, or still a known
placeholder in any letter case. Generate one with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`
(that prints 43 characters).
`DATA_COLLECTOR` picks the market-data collector behind fetch-company:
`yahoo` (live Yahoo Finance, the default) or `fake` (offline, synthetic).
With `yahoo`, fetch-company calls Yahoo through a guard
(`app/data_collectors/guard.py`): an in-memory cache, a rate limit and
retries. A repeat request within the cache time does not reach Yahoo,
and the data keeps its original retrieval time (fetch-company does not
store that time yet). A "not found" answer is cached too, but only for
`COLLECTOR_CACHE_TTL_NO_DATA_SECONDS` (5 minutes by default), because
Yahoo can report a hidden failure as no data. The cache and the rate
limit belong to one process (several workers each get their own limit),
the cache starts empty, and changed settings apply after a restart.
A full rate limit, or a provider error after the last retry, returns
502 `Data provider error`. The rate-limit wait and the retry sleeps of
one call share `COLLECTOR_TOTAL_DEADLINE_SECONDS`, so they cannot stack.
At most `COLLECTOR_MAX_INFLIGHT` provider calls run at once; another
call fails immediately instead of waiting. A cache hit does neither.
Each Yahoo HTTP request times out after 10 seconds
(`YFINANCE_HTTP_TIMEOUT_SECONDS`), and several requests inside one call
share the time the deadline has left. The limits, with their defaults:

| Setting | Default | Meaning |
|---|---|---|
| `COLLECTOR_CACHE_TTL_COMPANY_INFO_SECONDS` | 86400 | Cache time for company profiles. `0` turns it off. |
| `COLLECTOR_CACHE_TTL_KEY_METRICS_SECONDS` | 3600 | Cache time for key metrics. |
| `COLLECTOR_CACHE_TTL_PRICE_HISTORY_SECONDS` | 900 | Cache time for price history. |
| `COLLECTOR_CACHE_TTL_FUND_ATTRIBUTES_SECONDS` | 86400 | Cache time for fund data. |
| `COLLECTOR_CACHE_TTL_NO_DATA_SECONDS` | 300 | Cache time for a "not found" answer; never longer than that data's own cache time. `0` turns it off. |
| `COLLECTOR_CACHE_MAX_ENTRIES` | 256 | The least recently used entry is dropped beyond this. |
| `COLLECTOR_RATE_LIMIT_CALLS` | 30 | Provider calls allowed per period. |
| `COLLECTOR_RATE_LIMIT_PERIOD_SECONDS` | 60 | Length of the rate-limit window. |
| `COLLECTOR_RATE_LIMIT_MAX_WAIT_SECONDS` | 5 | How long a call may wait for a free slot. |
| `COLLECTOR_RETRY_MAX_RETRIES` | 2 | Retries for a temporary provider error. |
| `COLLECTOR_BACKOFF_BASE_SECONDS` | 1 | Ceiling of the first random retry delay. |
| `COLLECTOR_BACKOFF_MAX_SECONDS` | 8 | Largest retry delay ceiling. |
| `COLLECTOR_TOTAL_DEADLINE_SECONDS` | 15 | Shared budget for the waits and retries of one call. |
| `COLLECTOR_MAX_INFLIGHT` | 4 | Provider calls allowed to run at the same time. |

`ALLOWED_HOSTS` is enforced, so a request with any other Host gets
400 Invalid host header.
`DEBUG` defaults to false. Set `DEBUG=True` in `.env` only when you need
`/api/v1/test-config`. `BACKEND_CORS_ORIGINS` is a comma-separated list
of http(s) origins. A JSON list works too. The code default for
`DATABASE_URL` is
`postgresql://investment_ai@localhost:5432/investment_ai`.

4. Start the API on loopback:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

`python main.py` binds `127.0.0.1:8000` as well. Open API docs at
`http://127.0.0.1:8000/docs`.

## API Routes

For the isolated local demo, curl examples, and lifecycle commands, see
[API demo guide](docs/api-demo.md). The demo runs on loopback only and uses
synthetic data; it is not a production deployment.

See [Reusable Synthetic Demo Data](docs/demo-data.md) for the versioned fixture,
read-only preview, and explicit, non-overwriting seed command.

- Root metadata: `GET /`
- Company endpoints: `/api/v1/companies`
- Financial metrics endpoints: `/api/v1/financial-metrics`
- Data collection endpoints: `/api/v1/data-collection`

## Tests And Quality Checks

From the repository root, after the virtual environment in Setup exists, run
the test suite. No `.env` file is required. Tests use the in-memory SQLite
database in `tests/conftest.py` and do not call market-data or AI providers.
GitHub Actions on Python 3.12 installs `requirements-dev.lock` with
`pip install --require-hashes`, runs pytest, prints a coverage report
for `app`, `main`, and `scripts`, and treats `DeprecationWarning` as an
error. The job fails if total coverage drops below 80%. Every `uses:`
action is a full commit SHA with a trailing `# vX.Y.Z` comment. A new
workflow uses that same form.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80
```

The command above includes `--cov-fail-under=80`, so running only part of the suite with that command fails the coverage gate. Drop `--cov-fail-under=80` to check a subset:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning tests/test_yahoo_finance_collector.py
```

### PostgreSQL integration tests

The default command above stays on SQLite. It does not need PostgreSQL, and it deselects tests marked `integration`. A node id does not turn that marker off: this still deselects the test and exits 5 unless `-m integration` is passed too.

```bash
python -m pytest tests/integration/test_postgres.py::test_server_is_postgresql
```

To run the PostgreSQL tests, set `TEST_POSTGRES_DSN` to a separate local database. The database name must contain `test` as its own word, separated by underscores (`investment_test`, `test_db`). Names such as `investment_ai`, `testing`, and `testdb` are refused. The host must be `localhost`, `127.0.0.1`, `::1`, or a Unix socket. `TEST_POSTGRES_ALLOW_REMOTE=1` allows another host and does not relax the name rule. The harness also refuses the application's `DATABASE_URL`, including a value read from `.env` without applying that file (the code default uses database name `investment_ai` on localhost), because it drops and recreates its tables. Query parameters `dbname`, `database`, `hostaddr`, and `service` are refused. A `host` query parameter must be loopback or an absolute socket path. `PGHOSTADDR` must be a loopback address, and `PGSERVICE` is refused, even when the URL already names a host, because libpq still applies them. `PGHOST` is checked only when the URL has no host. If the variable is unset, `pytest -m integration` skips the database tests with a message. `REQUIRE_POSTGRES=1` (set in CI) makes a missing variable fail the run.

`pytest -m integration` imports the application from an empty directory before any test module imports it, so a `.env` file in the repository or the current directory is not applied to `Settings`. A `DATABASE_URL` exported in the shell is still read. The default SQLite command does not take that path.

```bash
createdb investment_test
TEST_POSTGRES_DSN=postgresql://127.0.0.1:5432/investment_test \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  -W error::DeprecationWarning -m integration
```

GitHub Actions uses this pinned image, the same digest as the `postgres:16.15` image that job pulled, and database `investment_test`. A local Docker server is the same image and the same `TEST_POSTGRES_DSN` contract:

```bash
docker run --rm -d --name iac-test-postgres \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=investment_test \
  -p 5432:5432 \
  postgres:16.15@sha256:ca0bd484cb98bf4b24eb1010e73fb3fcbd6714d240fbc1a10eea5b7dbecb641d
TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test \
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  -W error::DeprecationWarning -m integration
```

The CI workflow runs that marked subset as a second job. The SQLite job is unchanged, including the 80% coverage gate. Tables in the integration tests are created from the SQLAlchemy models. Alembic upgrade and downgrade on PostgreSQL remains issue #8.

Useful lint and formatting checks, run from the repository root. Black and
isort read line length 79 from `pyproject.toml`. flake8 does not read that
file; `.flake8` records the same 79, which is also flake8's own default.
These commands do not pass `--line-length`. `black --check` passes on
these paths. isort and flake8 still report the previous import-order,
unused-import, and long-line findings. Black does not rewrite those
docstrings and comments. CI runs pytest and does not run these checks.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check app main.py setup_database.py tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only app main.py setup_database.py tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 app main.py setup_database.py tests
```

## License

MIT
