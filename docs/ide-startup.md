# Run And Debug The Backend In An IDE

The current application is a FastAPI backend with Swagger, not a separate
frontend. Investor profiles and AI analysis are not implemented. This guide
describes local development, not a public deployment: there is no authentication.

## 1. Open The Correct Source And Interpreter

Open the checkout containing this guide in PyCharm (**File > Open**). The
recovery worktree from the September session is
`$TMPDIR/investment-pr-delivery`; temporary directories can disappear, so
prefer a persistent checkout for ongoing work.

In **Settings > Project > Python Interpreter**, select an existing Python 3.12
interpreter. On the original development machine it is:

```text
~/projects/Investment-AI-Companion/.venv/bin/python
```

Reusing this interpreter does not select its source checkout. For another
machine, create a Python 3.12 virtual environment and install the hashed
dev lock:

```bash
python -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
```

That command was checked on Python 3.12.3 with the lock in this branch.
Use `requirements.lock` instead when the environment only runs the API.
Do not upgrade an existing environment merely to follow this guide.

## 2. Prepare A Dedicated Local Database

Use a dedicated, disposable PostgreSQL database, never a production database.
The September demo used a private Unix socket and temporary database files.
Those paths are historical and must not be assumed to survive cleanup/reboot.
See [API demo lifecycle](api-demo.md) if that cluster still exists. If it does
not, provision a new local database before continuing. Do not run `initdb`
against an existing cluster or point the API at an unrelated database.

For an already running local PostgreSQL server, the following terminal commands
create a new, dedicated login and database. They require a PostgreSQL administrator
login; replace `YOUR_LOCAL_PG_ADMIN` and the port with your local configuration.
Choose unused names and stop on errors, rather than reusing an unknown database.

```bash
createuser -h 127.0.0.1 -p 5432 -U YOUR_LOCAL_PG_ADMIN -P iac_demo
createdb -h 127.0.0.1 -p 5432 -U YOUR_LOCAL_PG_ADMIN -O iac_demo iac_demo
```

The password prompt avoids putting the password in shell history. The resulting
SQLAlchemy URL has the form
`postgresql://iac_demo:URL_ENCODED_PASSWORD@127.0.0.1:5432/iac_demo`.
Percent-encode special characters in the password. Keep the URL local and do not
commit it. Installing/initializing a PostgreSQL server is a prerequisite, not
performed by these commands. Redis, Elasticsearch and provider keys are not
required for the company/financial-metrics CRUD walkthrough.

## 3. Create A Run/Debug Configuration

Create an empty local runtime directory outside the source checkout, for example
`$HOME/.local/share/investment-ai-demo`. It must not contain `.env`; the app loads
that filename relative to its working directory. Resolve `$HOME` to the actual
absolute path in IDE fields.

Choose **Run > Edit Configurations > + > Python** and set:

| Field | Value |
| --- | --- |
| Name | `Investment API local` |
| Target type | Module name |
| Module name | `uvicorn` |
| Parameters | `main:app --host 127.0.0.1 --port 8082` |
| Interpreter | The Python 3.12 environment selected above |
| Working directory | Your empty runtime directory |

Disable inherited system environment variables, automatic content/source roots
in `PYTHONPATH`, and any IDE `.env` loader. Add these environment variables as
individual entries, with literal values and no shell quoting:

| Variable | Value |
| --- | --- |
| `PYTHONPATH` | Absolute path to the checkout containing this guide |
| `PATH` | `/usr/bin:/bin` (macOS/Linux) |
| `PYTHONDONTWRITEBYTECODE` | `1` |
| `DATABASE_URL` | Your dedicated PostgreSQL URL from step 2 |
| `DEBUG` | `False` |
| `BACKEND_CORS_ORIGINS` | `[]`, or a comma-separated origin list |
| `OPENAI_API_KEY` | Empty |
| `SECRET_KEY` | Required. A locally generated random value |

Generate the secret using the selected interpreter:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Paste the result into the field; IDE fields do not evaluate shell commands.
Keep this configuration local, not committed. Other Python IDEs need the same
interpreter, module, arguments, working directory and environment values.

`python main.py` binds `127.0.0.1:8000`. This IDE configuration uses port
8082 on the same loopback address. `BACKEND_CORS_ORIGINS` accepts a
comma-separated list (`http://localhost:3000,http://127.0.0.1:3000`) or a
JSON list. `[]` means no browser origins. Startup fails when `SECRET_KEY`
is missing. `ALLOWED_HOSTS` defaults to `localhost` and `127.0.0.1` and is
enforced. Do not add `--reload` for debugging. `DEBUG=False` does not
disable IDE breakpoints.

## 4. Run And Verify

Click **Run**, then open [Swagger](http://127.0.0.1:8082/docs). Check the console
for database errors and make a database-backed request:

```bash
curl -q --noproxy '*' -fsS 'http://127.0.0.1:8082/api/v1/companies/?skip=0&limit=100'
```

An empty new database should return `[]`. Startup initializes tables through
`init_db()` during the application lifespan. A database initialization failure
aborts startup; fix the connection or permissions before restarting. Initialization
still uses `Base.metadata.create_all`, not Alembic migrations. The root endpoint
is not a continuous database health check after startup.

For debugging, set a breakpoint in a GET handler in `app/api/companies.py`, use
**Debug**, and request that endpoint. Resume execution to receive the response.
Stop only this IDE process with **Stop**; do not kill another API or database.
Port 8082 avoids the earlier demo's 8081; if occupied, choose a free port and
update all URLs. Two API processes using the same database see the same writes.

## 5. Load Test Data

From the checkout root, using the selected interpreter, preview first:

```bash
python -m scripts.seed_demo --base-url http://127.0.0.1:8082
# Only after verifying that this API uses your disposable database:
python -m scripts.seed_demo --base-url http://127.0.0.1:8082 --apply
```

The fixture adds six synthetic companies and 20 financial records. Repeated
application does not overwrite existing values. Run one seeder at a time;
multi-request writes are not atomic. See [demo data](demo-data.md) for details
and [API requests](api-demo.md) for curl examples, substituting port 8082.
Avoid external collection endpoints during synthetic testing; financial-metrics
ingestion is still a placeholder.

## Troubleshooting And Verification Limits

- Import errors: check interpreter, module target and explicit `PYTHONPATH`.
- Database errors: check PostgreSQL status, database ownership and the URL.
- Settings errors: ensure the working directory has no `.env` and CORS is `[]`. Check `SECRET_KEY` is at least 32 characters.
- Blank Swagger: CDN assets require network access; use curl or OpenAPI JSON.
- `/api/v1/test-config` returns 403: expected with `DEBUG=False`.
- No breakpoint: check Debug mode, route, port and source checkout; omit reload.
- Missing temporary files: recover committed code from Git and reprovision an
  isolated database. Fixtures restore baseline samples, not user edits.

IDE GUI execution, fresh dependency installation and new database provisioning
were not performed for this guide. Tests do not establish those workflows.
Field names vary by IDE version; see the
[JetBrains Python configuration reference](https://www.jetbrains.com/help/pycharm/run-debug-configuration-python.html).
