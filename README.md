# Investment AI Companion

Investment AI Companion is a FastAPI service for investment research workflows. It stores company data, financial metrics, and market-data collection results that can support analysis and decision hygiene.

The application must not present generated output as financial advice. Analysis features should show sources, data freshness, assumptions, risks, and uncertainty.

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
- A local virtual environment at `.venv`.
- Redis, Elasticsearch, OpenAI, news, and social-media credentials only when working on features that use them.

## Setup

For step-by-step IDE configuration, see [Run and debug in PyCharm](docs/ide-startup.md).
The application currently has a backend and Swagger UI, not a separate frontend.

1. Create and activate the virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
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

4. Start the API:

```bash
python -m uvicorn main:app --reload
```

Open API docs at `http://127.0.0.1:8000/docs`.

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
