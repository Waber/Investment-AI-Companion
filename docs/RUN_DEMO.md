# Run the demo

Short path to the local `/ui` pages. These commands were run on Linux
with Python 3.12.3. `python` was not on `PATH` before the virtualenv
existed, so the venv is created with `python3`. After activation,
`python` is the venv interpreter.

## Prerequisites

- Python 3.12 or newer.
- macOS or Linux. The lock files have no Windows markers (issue #53).
- git, and a checkout of this repository.

## Commands

From the repository root:

```bash
git checkout cursor/ui-skeleton-htmx-aa8b
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
```

Generate a key and keep it out of git. `token_urlsafe(48)` printed a
64-character value here. Anything shorter than 32 characters is
rejected, including the old placeholders.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
export SECRET_KEY="<paste the generated value>"
export DATABASE_URL="sqlite:///demo/investment_demo.db"
```

The same two lines in a gitignored `.env` file also work, because
settings read that file. Do not commit it. `ALLOWED_HOSTS` is not
required for this demo. The default is `localhost,127.0.0.1`.

```bash
python -m scripts.seed_demo --database-url "sqlite:///demo/investment_demo.db" --apply
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/ui](http://127.0.0.1:8000/ui).

`python main.py` binds `127.0.0.1` as well. The steps above use
uvicorn so the sqlite URL is the one just exported. Both the seed
and uvicorn need `SECRET_KEY`. The seed reads the sqlite path from
`--database-url` and does not open the default PostgreSQL URL.

## What you will see

The seed reports 6 companies created and 20 metric rows. The list
shows `DEMO_PL_TECH`, `DEMO_US_GROWTH`, `DEMO_DE_INDUSTRY`,
`DEMO_JP_STABLE`, `DEMO_SG_EARLY`, and `DEMO_PL_EMPTY`. Polish is
the default. The disclaimer starts with "Nie jest poradą
inwestycyjną". PL and EN switch the language with a cookie. English
says "It is not financial advice."

To reset, stop uvicorn, delete the file, and seed again:

```bash
rm -f demo/investment_demo.db
python -m scripts.seed_demo --database-url "sqlite:///demo/investment_demo.db" --apply
```

That second seed also created 6 companies and 20 metric rows.

## Troubleshooting

- Missing or too-short `SECRET_KEY`: startup fails before the server
  listens. The message says the key must be at least 32 characters
  and shows the `token_urlsafe(32)` generator. Known placeholders
  are rejected.
- `400` `Invalid host header`: the browser host is not
  `127.0.0.1` or `localhost`. Open
  [http://127.0.0.1:8000/ui](http://127.0.0.1:8000/ui). A request
  with `Host: evil.example` returned that 400.
- Port in use: uvicorn exits with `[Errno 98] error while attempting
  to bind on address ('127.0.0.1', 8000): address already in use`.
  Stop the other process or pick another port.
- Pip hash mismatch: `--require-hashes` refuses a file whose hash
  is not in `requirements.lock`. Install that lock as written. Do
  not drop the flag.

## Tests

Install the dev lock in the same venv, then run the CI command from
the repository root. Leave `DATABASE_URL` unset and do not leave a
`.env` file in the checkout.

```bash
python -m pip install --require-hashes -r requirements-dev.lock
python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80
```

PostgreSQL tests are optional. They are marked `integration`. With
`TEST_POSTGRES_DSN` unset, this command was run and reported
103 passed, 16 skipped, 1019 deselected. The 16 skips need a
database.

```bash
python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration
```

CI sets `REQUIRE_POSTGRES=1` and
`TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`.
The image is `postgres:16.15` with the digest in
`.github/workflows/tests.yml`. README has a `docker run` for that
image. `docker` is not installed in the environment where this page
was checked, so that `docker run` was not executed here.

## For the next agent

Read `AGENTS.md`, `docs/work-state.md`, and
`docs/product-requirements.md` before choosing work. Demo issues
use the `demo` label (#24 through #40). After this pull request,
the next items are #24, #19, #25, and #26. Post-demo work is
#54 through #58.
