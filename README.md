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

The environment template includes configuration keys for Redis, Elasticsearch, OpenAI, news, and social-media providers. Treat these as planned or configured integrations unless the corresponding application code exists and is covered by tests.

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
├── requirements.txt         # Python dependencies
└── setup_database.py        # Local database setup helper
```

## Requirements

- Python 3.12 for local development.
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

2. Install dependencies:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

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
GitHub Actions on Python 3.12 runs pytest, prints a coverage report
for `app`, `main`, and `scripts`, and treats `DeprecationWarning` as an
error. The coverage report does not fail the job.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing
```

Useful lint and formatting checks, run from the repository root. Black and
isort read `pyproject.toml`. flake8 does not read that file, so it reads
`.flake8`. All three use line length 79 from that configuration, so these
commands do not pass `--line-length`. Older application files still contain
formatting debt; the commands report it and do not reformat those files.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check app main.py setup_database.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only app main.py setup_database.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 app main.py setup_database.py
```

## License

MIT
