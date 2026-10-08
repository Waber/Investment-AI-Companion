# Development Journal

## 2026-10-08 - Review follow-up on requirements v0.3

- Scope: documentation only, one commit on top of `55cc070`. The
  disclaimer stays in both phases, including on post-demo signals.
  Only the no-buy/sell rule is demo-only. The hosting note is research
  input, not a decision. `docs/work-state.md` is unchanged.
- OVH: the heading "OVH VPS 2027 range" was left as written. OVHcloud's
  VPS page and the 2026 blog post "VPS 2027: OVHcloud's new server
  range" use that name. VPS-1 is the entry model in that range.
- AI model: Grok 4.7 (Cursor cloud agent). Account usage was not
  available in this session.

## 2026-10-08 - Product requirements v0.3 and hosting research

- Scope: documentation only, on a branch from `origin/master` `d568663`.
  `docs/product-requirements.md` is the Project Manager's v0.3 source,
  applied with the PM's v0.2-to-v0.3 diff on top of master.
  `docs/research/hosting-options.md` is the Researcher's hosting note,
  verbatim. No `.py` files, workflows, or config files were edited.
  `docs/work-state.md` is unchanged. The live next action stays #45
  and #47 together.
- Decision: "No authentication, no hosting" and "the score is never a
  buy/sell signal" apply to the demo phase only. Section 12 is the
  PM's post-demo direction (server for the owner, login, private
  holdings, scheduled scanner with signals and notifications).
  Refs #48, #56, #57 and #58. This does not close them.
- Merge with PR #51: two hunks did not apply on the #51 roadmap text.
  The P6 row and the dependency bullet that starts "On 2026-10-08 the
  Project Manager moved #11's security/deps part" stay exactly as on
  master, including the note that the `yfinance>=1.7` pin moved with
  that security/deps part. The P7 row, the issue map (#48, #54–#58),
  the P7 dependency line, and section 12 are the PM's wording.
- There is no `docs/research/README`. The hosting note has no relative
  links to rewrite.
- AI model: Grok 4.7 (Cursor cloud agent). Account usage was not
  available in this session.
- Verification: GitHub Actions Tests run 37833690203 succeeded on
  `786e1e0` (the content commit). Job `pytest (Python 3.12, SQLite)`
  completed with conclusion success.
  https://github.com/Waber/Investment-AI-Companion/actions/runs/37833690203

## 2026-10-08 - Integration client host and neutral paths (#9)

- Scope: follow-up on `cursor/postgres-integration-harness-fc54`
  after
  [Actions run 37836507848](https://github.com/Waber/Investment-AI-Companion/actions/runs/37836507848)
  went green on `c9b7302`. Pull request #61 is still open, so
  this branch is not rebased onto it.
- Decision, client host: `postgres_client` uses
  `base_url="http://127.0.0.1"`. #61 adds `TrustedHostMiddleware`
  that allows `localhost` and `127.0.0.1`. The name `testserver`
  would be HTTP 400 and would fail the PostgreSQL API tests
  after that merge. `tests/conftest.py` is still untouched.
- Decision, paths: text added by this pull request no longer
  contains a personal account name or a machine-specific home or
  temporary directory. DSN tests read the application default from
  `Settings.model_fields` instead of copying a role name. Example
  URLs use the role `user`. The README names the refused database
  as `investment_ai` on localhost. Historical journal and
  work-state paths that were already on master are left for #61,
  which rewrites those same lines. Rewriting them here would
  conflict with that edit.
- Not in this commit: the work-state sentence "#9 stays later".
  #61 adds that sentence in its new top section. This branch
  updates it when it rebases onto #61.
- Verification, same environment as the allowlist entry:
  default suite 846 passed, 68 deselected, exact 92.58%.
  `-m integration` with the local test DSN: 67 passed, 1
  xfailed. `black`, `isort --check-only`, and `flake8` passed
  on the touched Python files.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.
## 2026-10-08 - PostgreSQL harness review follow-up (#9)

- Scope: QA and PM follow-up on the harness in
  `cursor/postgres-integration-harness-fc54`, still based on
  `origin/master` `d568663`. The PM accepted the GitHub Actions
  service container and is editing issue #9. Alembic
  upgrade/downgrade on PostgreSQL moves to #8 and is not in this
  change. The disposable `scripts/test_postgres.py` runner and its
  cleanup tests are dropped. `.env` isolation before the
  application import stays in #9 and is in this change.
- Decision, allowlist: refusing only the application URL was not
  enough. The harness drops and truncates tables, so any other
  name would have been destroyed. `decide_test_dsn` now refuses a
  database name unless it contains `test` as its own word
  (`investment_test` passes; `testing`, `testdb`, and
  `investment_ai` do not). The host must be localhost,
  `127.0.0.1`, `::1`, or a Unix socket, unless
  `TEST_POSTGRES_ALLOW_REMOTE=1`. That override does not relax
  the name rule or the application-database check. The CI URL
  `postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  already passes, so the database was not renamed and the job
  does not set the override.
- Decision, image pin: the PostgreSQL job uses
  `postgres:16.15@sha256:ca0bd484cb98bf4b24eb1010e73fb3fcbd6714d240fbc1a10eea5b7dbecb641d`.
  That digest is the `postgres:16` image the earlier CI run
  pulled. The README tells a local Docker run to use the same
  image and `TEST_POSTGRES_DSN`.
- Decision, `.env` isolation: `Settings` reads `env_file=".env"`
  from the process working directory. pytest loads the repository
  root `conftest.py` before `tests/conftest.py`, and
  `tests/conftest.py` imports the application at module level.
  When the command selects the `integration` marker (pytest's own
  `-m` grammar; the last `-m` wins over `PYTEST_ADDOPTS`; no `-m`
  means this repo's addopts, which deselects the marker), the
  root conftest imports `app.core.config`, `app.core.database`,
  and `main` from an empty temporary directory. The later import
  reuses that module, so a `.env` in the original directory is
  not applied. A `DATABASE_URL` exported in the shell is still
  read. The default SQLite command does not select the marker, so
  it does not take this path. `tests/conftest.py` was not
  modified.
- Decision, issue #16: the current-behaviour test stays (duplicate
  `DUP` is 500, and `dup` is stored). A second test expects 400
  or 409 and one row, with `strict` xfail. When the fix lands,
  that marker has to be removed or the suite fails. A fixture
  setup error is not an expected failure.
- Docstring only: `SET TIME ZONE` stays after COMMIT. Only
  ROLLBACK reverts it. The `begin` listener still sets
  `Europe/Warsaw` on every transaction. Behaviour is unchanged.
- Verification, from the repository root, no `.env`,
  `DATABASE_URL` unset, Python 3.12.3, packages from
  `requirements-dev.lock`:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 846 passed, 68 deselected in 12.84s, no warnings summary,
  TOTAL 92% (exact 92.58%).
  Node id without the marker -> 1 deselected, exit 5.
  `-m integration` with `TEST_POSTGRES_DSN` unset -> 53 passed,
  15 skipped, exit 0. The 53 do not open PostgreSQL (45 DSN
  checks and 8 `.env` checks). The 15 database tests skip.
  The same command with
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  -> 67 passed, 1 xfailed, 846 deselected in 2.00s on the local
  PostgreSQL 16.15. The xfail is the #16 target test.
  `REQUIRE_POSTGRES=1` with the variable unset failed in fixture
  setup, exit 1.
  `black --check`, `isort --check-only`, and `flake8` passed on
  `conftest.py` and `tests/integration`.
  GitHub Actions
  [run 37836507848](https://github.com/Waber/Investment-AI-Companion/actions/runs/37836507848)
  on `c9b7302`: SQLite job 846 passed, 68 deselected in 17.49s,
  TOTAL 93%. PostgreSQL job 67 passed, 1 xfailed, 846 deselected
  in 2.68s on PostgreSQL 16.15 (Debian 16.15-1.pgdg13+2).
- Work-state next action: unchanged. #45 and #47 together, with
  #50 if that fix stays small. Then #24, #19, #25, and #26 (with
  #16 and #17). #8 and #16 stay open. #20 stays open until
  review accepts the PostgreSQL run.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - PostgreSQL integration test harness (#9)

- Scope: issue #9, on a branch from `origin/master` `d568663`.
  Branch `cursor/postgres-integration-harness-fc54`.
  Implementation commit `e242341`. SQLite stays the default
  database. No new package. Alembic is unchanged.
- Decision, opt-in: tests under `tests/integration/` carry the
  existing `integration` marker. `addopts` still passes
  `-m "not integration"`. `python -m pytest` deselects them.
  `pytest -m integration` replaces that expression and runs them.
  A node id without `-m integration` stays deselected and exits 5.
- Decision, configuration: the database URL is
  `TEST_POSTGRES_DSN`. When it is unset, database fixtures skip
  with a message that names the variable and an example URL.
  `REQUIRE_POSTGRES=1` (the CI job) fails that case instead of
  skipping, so a missing CI variable cannot go green on skips.
  DSN comparison tests in `tests/integration/test_postgres_dsn.py`
  do not open a connection, so they still run when the variable
  is unset.
- Decision, refuse the application database: the harness compares
  the test URL with `settings.DATABASE_URL` and with the code
  default (database name `investment_ai` on localhost).
  The same host (localhost, 127.0.0.1, ::1, or a Unix socket),
  port, and database name match even when the role or the driver
  suffix differs. A match fails the run before any connection.
  The tests then drop and recreate only their own tables.
- Decision, schema: `Base.metadata.create_all` on the test
  engine. Issue #8 is still open. `alembic.ini` has
  `version_num_format = %04d`, which crashes Alembic commands
  (the value needs `%%04d`). There is no baseline revision. The
  integration test asserts `alembic_version` is absent and that
  `period_end` is `timestamp with time zone`.
- Decision, CI: a second job, `pytest (Python 3.12, PostgreSQL)`,
  uses a `postgres:16` service container and
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`.
  The SQLite job is unchanged: same checkout SHA,
  `persist-credentials: false`, hashed install from
  `requirements-dev.lock`, and the same pytest flags including
  `--cov-fail-under=80`. The PostgreSQL job does not pass
  coverage flags. No `pytest-postgresql` dependency.
- Decision, session zone: each transaction runs
  `SET TIME ZONE 'Europe/Warsaw'`. December is UTC+1 there, so a
  value shifted into the session zone does not read back as the
  UTC instant. The server default can stay UTC.
- Behaviour pinned on PostgreSQL: `+02:00`, `Z`, and naive
  `period_end` read back as the UTC instant through the API and
  the ORM, and as the UTC wall clock from
  `period_end AT TIME ZONE 'UTC'`. Five other spellings of
  `2025-12-31T00:00:00Z` return 400 with the uniqueness detail,
  and one row remains (issue #20). A direct ORM insert of that
  same instant raises `IntegrityError` on
  `uq_metrics_company_period`. A missing company is 400 from the
  API and `IntegrityError` from a direct insert. `DELETE FROM
  companies` is rejected by `financial_metrics_company_id_fkey`
  while metrics exist. Deleting the company through the ORM
  removes the metrics. After that constraint error, the same
  session can commit a new row.
- Issue #16 is recorded, not fixed. A second company with ticker
  `DUP` returns 500 and `{"detail":"Internal server error"}`.
  Ticker `dup` is stored as a second row.
- `tests/conftest.py` was not modified. The SQLite `client`
  fixture is untouched. PostgreSQL fixtures live in
  `tests/integration/conftest.py`: `postgres_engine` (session),
  `postgres_session_factory` (truncates `companies` and
  `financial_metrics` around each test), and `postgres_client`
  (async HTTP client, `init_database_on_startup=False`). The
  only edit under the existing tests tree is the docstring in
  `tests/test_known_defects.py`, which now points at the
  PostgreSQL duplicate-instant test.
- Out of this pull request: the disposable local cluster runner
  (`scripts/test_postgres.py`) and Alembic upgrade/downgrade.
  The runner would be a new script under `scripts/`, which is
  inside the coverage gate, and the task asked for the GitHub
  Actions service container instead of a Python-managed server.
  Migrations wait for #8.
- Verification, from the repository root, no `.env`,
  `DATABASE_URL` unset, Python 3.12.3, packages from
  `requirements-dev.lock`:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 846 passed, 37 deselected in 13.55s, no warnings summary,
  TOTAL 92% (exact 92.58%). Same passed count as master
  `d568663`.
  Node id without the marker:
  `python -m pytest -q -p no:cacheprovider tests/integration/test_postgres.py::test_server_is_postgresql`
  -> 1 deselected, exit 5.
  `python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning -m integration`
  with `TEST_POSTGRES_DSN` unset -> 23 passed, 14 skipped,
  exit 0. The skip text is: PostgreSQL integration tests need
  `TEST_POSTGRES_DSN` set to a database that is not the
  application's `DATABASE_URL`.
  The same `-m integration` command with
  `TEST_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/investment_test`
  -> 37 passed, 846 deselected in 1.06s.
  Server version from that run: `PostgreSQL 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1) on x86_64-pc-linux-gnu, compiled by gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0, 64-bit`.
  Pointing `TEST_POSTGRES_DSN` at the code default, and setting
  `REQUIRE_POSTGRES=1` with the variable unset, each failed in
  fixture setup before a connection, exit 1.
  `black`, `isort --check-only`, and `flake8` passed on
  `tests/integration` and `tests/test_known_defects.py`.
  The docs tree, measured before this commit: 846 passed,
  37 deselected in 13.00s, exact 92.58%.
  GitHub Actions on `8bfd7ba`
  ([run 37834076658](https://github.com/Waber/Investment-AI-Companion/actions/runs/37834076658)):
  SQLite job 846 passed, 37 deselected in 9.90s, TOTAL 93%.
  PostgreSQL job 37 passed, 846 deselected in 1.20s.
  Service version: `PostgreSQL 16.15 (Debian 16.15-1.pgdg13+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 14.2.0-19) 14.2.0, 64-bit`.
- Work-state next action: unchanged. #45 and #47 together, with
  #50 if that fix stays small. Then #24, #19, #25, and #26 (with
  #16 and #17). This harness is done. #8 and #16 stay open.
  #20's PostgreSQL check now has a test; the issue stays open
  until review accepts that run.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - Security dependencies, hashed locks, and Actions SHAs (#11, #46)

- Scope: the security/deps part of #11, on a branch from
  `origin/master` `7120577`. Branch
  `cursor/security-deps-hashed-lock-79f1`.
  [PR #51](https://github.com/Waber/Investment-AI-Companion/pull/51).
  #46 is included because the workflow file changed. No Gemini
  adapter, no UI, and no yfinance cache or throttle adapter.
- Decision, one pull request: FastAPI 0.104.1 to 0.143.0 still uses
  Pydantic v2 (locked 2.13.5, floor `>=2.9.0,<3`). Starlette is
  locked at 1.7.0. The suite needed one test change. That is not a
  Pydantic major bump and not a broad behaviour rewrite, so black,
  pytest, yfinance, the removals, the split, and the lock stay in
  this pull request. A follow-up pull request was not opened.
- Decision, Starlette floor: the three named CVEs are fixed in
  0.36.2, 0.40.0, and 0.47.2. The direct pin is `starlette>=1.3.1`
  so resolution also clears the later Starlette advisories that
  pip-audit reports for the 0.x line, through CVE-2026-54283.
  FastAPI 0.135.2 is the first line whose own floors are
  `starlette>=0.46.0` and `pydantic>=2.9.0`. The lock selects
  FastAPI 0.143.0, which allows Starlette 1.7.0.
- Decision, pytest-asyncio: async tests and `tests/conftest.py`
  use `pytest_asyncio` fixtures, so the plugin stays. 0.21.1 does
  not run on pytest 8 or later. The dev file requires
  `pytest-asyncio>=1.0`. The lock installs 1.4.0, which accepts
  pytest 9. scikit-learn is removed. Nothing imports `sklearn`.
- Decision, jinja2 and python-multipart: not pinned. No module
  imports them, and there is no `/ui` template tree yet. D4 and D5
  add the pins when the UI needs them.
- Decision, google-genai: not pinned. It waits for the Gemini
  adapter. `pip install --dry-run google-genai` against the dev
  lock's environment would install `google-genai` 2.29.0. Installed
  FastAPI, Pydantic 2.13.5, httpx 0.28.1, and requests 2.34.2
  already satisfy it. The dry-run would downgrade `websockets`
  from 17.2 (pulled by yfinance 1.7) to 16.1.1, because
  google-genai 2.29.0 requires `websockets<17`. yfinance accepts
  `websockets>=13`, so 16.1.1 still fits. The adapter work should
  regenerate the lock with that constraint included.
- Decision, pandas and numpy: tests import pandas, so
  `requirements-dev.txt` pins `pandas>=1.3.0` (locked 3.0.6).
  numpy is only an `importorskip` in one test. The direct numpy
  pin is removed. yfinance pulls numpy 2.5.3, so that test runs.
  beautifulsoup4 is the same kind of transitive pin: removed as a
  direct requirement, present as 4.15.0 because yfinance needs it.
- Removed direct pins, after grep showed no import under `app/`,
  `main.py`, `scripts/`, or `tests/`: aiohttp, nltk, python-jose,
  passlib, bcrypt, openai, selenium, pandas-datareader, spacy,
  elasticsearch, redis, sphinx, sphinx-rtd-theme, scikit-learn.
  `REDIS_URL`, `ELASTICSEARCH_URL`, and `OPENAI_API_KEY` remain
  settings fields. They are strings, not client libraries.
- httpx stays, in the dev file. Tests use `httpx.AsyncClient` and
  `ASGITransport`. The application does not import httpx.
- Code change: `tests/test_validation_errors.py` calls
  `ValidationError.errors(include_url=False)`. FastAPI 0.143
  builds the request error that way, so the 422 body has no
  Pydantic documentation link. The custom handler still encodes
  the errors FastAPI passes in.
- Client-visible behaviour from FastAPI 0.143 and Starlette 1.7,
  checked against the installed app: when `BACKEND_CORS_ORIGINS`
  is set, every response includes `Vary: Origin`, including a
  request that sends no `Origin` header. An empty CORS list does
  not add that header. A CORS preflight's
  `Access-Control-Allow-Methods` includes `QUERY` (with DELETE,
  GET, HEAD, OPTIONS, PATCH, POST, and PUT). The OpenAPI
  `ValidationError` schema includes `input` and `ctx`. The
  `/api/v1/test-config` 200 schema sets `additionalProperties` to
  true. A 422 detail object has `type`, `loc`, `msg`, and `input`.
  It no longer includes `url`.
- Python 3.12 is the minimum. The locked numpy 2.5.3 declares
  `Requires-Python >=3.12`.
- `--strip-extras` on the runtime compile does not change pins or
  hashes, so `requirements.lock` was left as compiled without that
  flag. The same flag on the dev compile changes one line,
  `coverage[toml]==7.16.2` to `coverage==7.16.2`, and the hashes
  stay the same. `requirements-dev.lock` was regenerated with the
  flag. The documented commands pass `--strip-extras`.
- History: four commits, and each one passes the CI pytest
  command. The dependency commit carries the requirements split,
  both hashed locks, the workflow change to
  `pip install --require-hashes -r requirements-dev.lock`, and the
  `include_url=False` test fix. Action tags stay on that commit.
  The CI commit pins `actions/checkout` and `actions/setup-python`
  to commit SHAs. The style commit is the Black 26 reformat only.
  Docs are last. Per-commit results are in the verification
  section below.
- Black 26.10.0 reformatted 14 legacy files in its own commit.
  `black --check` then passes on `app`, `main.py`,
  `setup_database.py`, and `tests`. isort and flake8 still report
  the previous import-order, unused-import, and long-line findings
  on those paths. CI runs pytest and does not run the linters.
- Gaps between the floor in the text files and the locked install:
  FastAPI 0.143.0 (floor 0.135.2), Starlette 1.7.0 (floor 1.3.1),
  Pydantic 2.13.5 (was 2.6.1, floor `>=2.9.0,<3`), python-dotenv
  1.2.4 (floor 1.2.2), requests 2.34.2 (floor 2.33.0), pytest
  9.1.1 (floor 9.0.3), pytest-asyncio 1.4.0 (floor 1.0), pytest-cov
  7.1.0 (floor 4.1.0), black 26.10.0 (floor 26.3.1), httpx 0.28.1
  (floor 0.25.2), pandas 3.0.6 (floor 1.3.0), yfinance 1.7.0
  (floor 1.7), pip-tools 7.6.2 (floor 7.0). Exact pins that match
  the lock: uvicorn 0.24.0, pydantic-settings 2.1.0, SQLAlchemy
  2.0.23, psycopg2-binary 2.9.9, alembic 1.12.1, isort 5.12.0,
  flake8 6.1.0, mypy 1.7.1.
- The previous flat `requirements.txt` installs on Python 3.12.
  GitHub Actions run
  [37780801408](https://github.com/Waber/Investment-AI-Companion/actions/runs/37780801408)
  on master `7120577` installed that file on Python 3.12 and the
  Tests job succeeded. The new dev lock also installs on Python
  3.12. A clean venv whose pip was 24.0 accepted
  `pip install --require-hashes -r requirements-dev.lock` and the
  same command for `requirements.lock`.
- Verification, from the repository root, no `.env`,
  `DATABASE_URL` unset, Python 3.12.3, packages from the dev lock:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 846 passed in 12.42s, no warnings summary, TOTAL 92% (exact
  92.58%). The 80% gate passed. `coverage report --precision=2`
  reports the same total. Collector tests are in that run and stay
  offline. `pip-audit -r requirements.lock` and
  `pip-audit -r requirements-dev.lock` both reported no known
  vulnerabilities. CI runs pytest only, so these checkouts were
  not asked to pass black, isort, or flake8. Each commit was
  checked out and the command above was run in a Python 3.12.3
  virtualenv installed with
  `pip install --require-hashes -r requirements-dev.lock` from
  that commit. The lock blob is the same on every commit
  (`9b70931`). No warnings summary on any run. Exact coverage
  is 92.58% on every run (`coverage report --precision=2`).
  `a585a01` (deps): 846 passed in 12.75s.
  `912c12b` (Actions SHAs): 846 passed in 12.57s.
  `3bbea71` (Black): 846 passed in 12.79s.
  The docs tree, measured before this commit: 846 passed in
  12.92s.
- Work-state next action: #45 and #47 together, with #50 if that
  fix stays small. Then #24, #19, #25, and #26 (with #16 and #17).
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - Fetch-company 500 detail and debt_to_assets (#18, #21)

- Scope: bugs #18 and #21, on a branch from `origin/master` `a03ca24`.
  Branch `cursor/fetch-company-500-debt-to-assets-9f95`.
  [PR #49](https://github.com/Waber/Investment-AI-Companion/pull/49).
  No global exception middleware. No Yahoo change besides the
  `debt_to_assets` mapping. `fetch-financial-metrics` stays a
  placeholder.
- Decision for #18: the 500 detail is the fixed string
  `Error fetching company data`. The handler uses `logger.exception`,
  so the traceback stays in the server log, and the log message
  includes the ticker. The ticker is read before the `try`, so the
  log can name it. 404 (empty provider payload) and 400 (`ValueError`,
  including "Company name or ticker already exists") are the same
  handlers as before.
- Decision for #21: `debt_to_assets` is `totalDebt / totalAssets` when
  both values are already on the `info` dict that `fetch_key_metrics`
  just loaded. `totalDebtPerShare` is a currency amount per share, so
  the mapping never reads it. There is no second provider call. If
  either total is missing, is not an int or float (booleans count as
  not numbers, because `bool` is a subclass of `int`), or total assets
  is zero, the ratio is `None`. With yfinance 1.7, `info` has no
  `totalAssets` for equities. QA checked AAPL and PKN.WA, so
  `debt_to_assets` will be `None` for equities. For ETFs such as SPY,
  `totalAssets` is assets under management, not a balance-sheet
  figure. A real ratio needs `balance_sheet` ('Total Debt' /
  'Total Assets'), which is planned for #24.
- Reviewer nits on the ratio: NaN and infinity are None, and so are
  negative debt and a non-positive asset total. `OverflowError` from
  a huge int is caught, so the other metrics stay. `numbers.Real`
  accepts NumPy numbers and still rejects bool. Local suite after
  that: 846 passed in 15.09s, TOTAL 92% (exact 92.75%).
- Test-first commits, then the fix. On `6a7f533`, QA's two strict
  xfails were `2 xfailed`. With `--runxfail` both failed as
  `AssertionError`: the 500 body contained `hunter2`, and
  `debt_to_assets` was `7.5`. On `a06ca28` the further tests were
  `8 failed`, `2 passed`, `2 xfailed`. The failures were assertion
  failures: the error log did not contain the ticker `FAIL`, and
  `debt_to_assets` was still `7.5` instead of `0.25`, `0.0`, or
  `None`. `test_fetch_company_404_and_400_stay_unchanged` already
  passed. The fix commit removes both xfail markers.
- `app/api/data_collection.py` and
  `app/data_collectors/yahoo_finance.py` were reformatted in their own
  commit (`4bb8f1f`) because Black, isort, and flake8 have to pass on
  every file the fix touches, and both files already failed that
  check. Unused imports were removed in that same commit. The 500
  detail and the per-share mapping were still the old code there.
- Verification, from the repository root, no `.env`, `DATABASE_URL`
  unset:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 838 passed in 15.33s, no warnings summary, TOTAL 92% (exact
  92.70%). The 80% gate passed. `coverage report --precision=2`
  reports the same total. Black, isort, and flake8 (line length 79)
  pass on the files this change touches. CI on `526990d`:
  [run 37778103776](https://github.com/Waber/Investment-AI-Companion/actions/runs/37778103776),
  838 passed in 23.14s, TOTAL 92% (exact 92.70%).
- Work-state next action, after the security review: #11, the
  security/deps part (FastAPI and Starlette CVE upgrade, `requests`,
  `python-dotenv`, `black`, `pytest`, removing unused pins,
  `yfinance>=1.7`, and a lock file with hashes). After it come #45
  and #47 together (secure config defaults and neutral defaults, one
  pull request), then #24, #19, #25 and #26 (with #16 and #17). #46
  (pin Actions to SHAs) goes into any pull request that touches CI.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - SQLite UTC timestamps and foreign keys (D1, #23 and #20)

- Scope: demo slice D1 from `docs/product-requirements.md` section 5
  ("Other model points") and section 11 phase P1, together with bug #20.
  Rebased onto `origin/master` `f8266ea`.
  [PR #22](https://github.com/Waber/Investment-AI-Companion/pull/22)
  is merged as `778735e`.
  [PR #41](https://github.com/Waber/Investment-AI-Companion/pull/41)
  is merged as `07c30f6`.
  [PR #43](https://github.com/Waber/Investment-AI-Companion/pull/43)
  is merged as `f8266ea`. Branch
  `cursor/sqlite-utc-timestamps-foreign-keys-feb1`.
- `app/core/utc_datetime.py` adds `UTCDateTime`. On write it converts
  the value to UTC. On SQLite it then drops `tzinfo` and stores that
  UTC wall clock, because SQLite keeps the clock and throws away the
  offset. On read it attaches UTC. On PostgreSQL the bound value stays
  timezone-aware, so `timestamptz` is unchanged. `as_utc` is the shared
  helper: a naive datetime is treated as UTC, an aware one is converted
  with `astimezone` so the instant stays the same.
- Decision for naive `period_end`: treat it as UTC. The API already
  accepts offset-less strings such as
  `2024-12-31T00:00:00` (see `tests/test_metric_creation_conflicts.py`).
  Rejecting them would break that contract. The same instant sent as
  `Z` or as `+02:00` is a duplicate (400). On PostgreSQL, naive
  `period_end` input used to be interpreted in the session time zone
  and is now UTC. Responses now always use the `Z` suffix.
- The metrics repository calls `as_utc` before the uniqueness pre-check
  and before the insert or update. `FinancialMetricsUpdate` accepts an
  optional `period_end` so an update can move the period and still hit
  that check. A row is not a duplicate of itself (`exclude_id`).
  An explicit JSON null is rejected because the update field is a
  `datetime` with default `None` (HTTP 422). Omitting it leaves the
  field unset, so the column stays unchanged. OpenAPI drops that null
  default and shows `period_end` as a non-nullable date-time. On
  master, `PUT` with null `period_end` returned 200 and the value was
  ignored. At `c3c8911` null reached the database and came back as 400
  `constraint violation`. `PUT` can move `period_end`. Moving onto an
  existing company, period, and type is 400.
- `create_db_engine` in `app/core/database.py` runs
  `PRAGMA foreign_keys=ON` on each SQLite connection. The test client
  uses that function, so the pragma is not copied into `tests/conftest.py`.
  The foreign-key test builds its own engine and does not use the
  `client` fixture.
- `scripts/seed_demo.py` still requires an offset on fixture rows.
  Rows read back from the API may be naive; those are matched as UTC,
  so `python scripts/seed_demo.py --apply` (with the required
  `--base-url` and the repo on `PYTHONPATH`) can run twice against a
  fresh SQLite file. The second run creates nothing.
- Test-first commits, then the fix: the strict xfail for #20
  (`1 xfailed` on the parent of the fix), then eight failing #23/#20
  tests (`8 failed`), then this change removes the xfail marker.
  QA verified #20 on PostgreSQL 16 (session timezone Europe/Warsaw)
  at the application level: the same instant with `+02:00`, `Z`, or
  naive returns 400, and readback has no double shift. The formal
  harness is still #9. Out of scope: Alembic (#8), that harness, the
  instrument model (#26), and bugs #18, #19, and #21.
- `app/models/database_models.py`, `app/models/financial_metrics.py`,
  and `app/repositories/financial_metrics_repository.py` were
  reformatted because Black, isort, and flake8 have to pass on every
  file this change touches, and those three already failed that check.
  Untouched files with the same old debt were left alone.
- QA's carried-over nit: #43 added the README sentence "CI does not
  run these lint checks yet".
- Verification, from the repository root, no `.env`:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 822 passed in 14.80s, no warnings summary, TOTAL 92% (exact
  92.36%) on the rebased head `c3c8911`. The 80% gate passed.
  After the null `period_end` follow-up, the same command is
  823 passed in 15.55s, no warnings summary, TOTAL 92% (exact 92.41%).
  Reviewer follow-up on this branch: 825 passed in 15.31s, no warnings
  summary, TOTAL 92% (exact 92.35%). `database.py` is fully covered,
  including the non-SQLite branch of `create_db_engine`.
- Work-state next action: bugs #18 and #21, then #24. Bug #19 can be
  slotted in.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not
  measured. Account usage was not available in this session; no
  percentage recorded.

## 2026-10-08 - Reviewer nits on the merged coverage gate

- Scope: [PR #43](https://github.com/Waber/Investment-AI-Companion/pull/43)
  on `cursor/reviewer-nits-minimal-c3a6`, rebased onto `origin/master`
  `07c30f6`. [PR #22](https://github.com/Waber/Investment-AI-Companion/pull/22)
  is merged as `778735e`. [PR #41](https://github.com/Waber/Investment-AI-Companion/pull/41)
  is merged as `07c30f6`. Master's journal and work-state sections from
  those pull requests are kept. No production `.py` edits.
- `actions/checkout` sets `persist-credentials: false`. The Tests job
  never pushes, so the checkout token is not stored in `.git/config`.
- isort `known_first_party` is `app`, `main`, and `scripts`.
- The README lint section no longer names a file that fails isort. It
  says older files still have formatting debt.
- Work-state no longer says Code Reviewer approved `63822cd` and is
  waiting on Raul. That line now says PR #22 is merged as `778735e`.
  The live next action is the product-requirements section at the top
  of `docs/work-state.md`.
- Verification: no `.env`, Python 3.12.3, pytest 7.4.3. Command:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  Result on this head: `813 passed in 11.32s`, TOTAL exact `91.77%`.
  `--cov-fail-under=80` passed.
- Lint comparison, same interpreter, from the repository root.
  `python -m isort --check-only --diff .` still fails 12 files, and the
  diff is identical with or without `known_first_party`.
  `python -m black --check .` would reformat 15 files, and
  `python -m flake8 .` reports 388 findings. Those two counts do not
  change when the isort setting is removed. The setting matters when
  isort runs outside the repo root, for example an IDE or pre-commit
  whose settings file is not this repository. Without
  `known_first_party`, isort treats `app` as third-party and regroups
  `app/api/companies.py`, placing the `app` imports in the same group
  as FastAPI and SQLAlchemy. With the setting, those imports stay in
  the first-party group.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
  Account usage was not available in this session; no percentage recorded.

## 2026-10-08 - Product requirements and research docs

- Scope: documentation only. Add Raul's product requirements (draft v0.2,
  2026-10-08) and the two research notes from the same day. Paths match
  the Demo v1 issues (#23–#40, label `demo`):
  `docs/product-requirements.md`,
  `docs/research/market-data-sources.md`, and
  `docs/research/llm-comparison.md`. No `.py` files, workflows, or config
  files were edited.
- Decision: `docs/product-requirements.md` matches the PM's updated copy
  (2026-10-08), which fixes the research paths and makes N1 optional for
  A1. There were no `/workspace` paths.
- Work-state next action is Demo v1 issue #23 together with bug #20
  first, then bugs #18 and #21, then #24, then #25, then #26. Issues
  #8, #9, and #10 come after the demo.
- Verification: from the repository root, no `.env`,
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider`
  -> 758 passed in 6.48s, no warnings summary. This machine provides
  `python3` (3.12.3); `python` on `PATH` was that interpreter. Dependencies
  came from `requirements.txt` and were not changed.
- GitHub Actions Tests on `8ba25ee` succeeded:
  https://github.com/Waber/Investment-AI-Companion/actions/runs/37756800118
  Job `pytest (Python 3.12, SQLite)` completed with conclusion success.
  That run is from before this rebase. The final run on `973330b`
  succeeded:
  https://github.com/Waber/Investment-AI-Companion/actions/runs/37758000432
  The same job completed with conclusion success. Rebase-merge recorded
  that commit on master as `07c30f6`.
- After the rebase onto `778735e`, from the repository root, no `.env`:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  -> 813 passed in 11.50s, no warnings summary, TOTAL 92% (exact 91.77%).
  The 80% gate passed.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
  Account usage was not available in this session; no percentage recorded.
- Rebased onto `origin/master` `778735e`. PR #13 is merged as `a10e196`.
  PR #15 is merged as `b2541d7`. PR #22 is merged as `778735e`.
  PR #41 is merged as `07c30f6`.

## 2026-10-08 - Review notes on the coverage tests

- Scope: one commit on `cursor/coverage-threshold-80-c3a6` on top of
  `63822cd`. QA's two commits are unchanged. No production `.py` edits.
  The 80% gate is unchanged. Code Reviewer approved the earlier head.
  PR #22 is merged as `778735e`.
- `test_test_config_marks_missing_settings` only blanked four settings.
  `Settings` fills any name it was not given from the process environment,
  so `NEWS_API_KEY=x` made that optional mark present and the test failed.
  The test now calls `monkeypatch.delenv` for every name the endpoint
  reports and passes each of those fields (`None` or `""`). With
  `NEWS_API_KEY=x` exported, the test passes.
- `test_financial_statements_return_all_six_frames` now checks
  `set(STATEMENT_ATTRIBUTES) <= set(statements)`. A new statement key
  does not fail it. The entry below said an added key would fail; that
  was true before this commit.
- `debt_to_assets` is still not asserted. The comment now names GitHub
  issue #21.
- Each company-shaped pin listed in the entry below has the comment
  `# company-shaped pin, see #26`. Issue #26 is the instrument model.
- `datetime` imports in `tests/test_repository_edge_paths.py` are at the
  top of the module. The stray parentheses around `200` are gone.
- README: the copied command includes `--cov-fail-under=80`, so a subset
  run with that flag fails the gate. The README shows the same command
  without the flag.
- Raul explicitly chose the 80% coverage threshold on 2026-10-08 at
  10:48 Warsaw time, overriding the earlier 70% recommendation. The
  Project Manager relayed the decision. The gate stays
  `--cov-fail-under=80`. JUnit XML and the `MIN_TESTS` gate are still
  not enabled.
- The live next action is the product-requirements entry at the top of
  this journal: Demo v1 issue #23 together with bug #20 first, then bugs
  #18 and #21, then #24, then #25, then #26. Issues #8, #9, and #10 come
  after the demo.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
  Account usage was not available in this session; no percentage recorded.

## 2026-10-08 - Coverage gate at 80%

- Scope: QA's two commits, applied with `git am` on
  `cursor/coverage-threshold-80-c3a6` from `origin/master` `b2541d7`.
  Authorship stays `QA prototype <qa@local>`. No production `.py` edits.
  No test was rewritten after review. JUnit XML and the `MIN_TESTS` gate
  stay off.
- What the new tests cover: Yahoo Finance collector (a stand-in for
  `yfinance.Ticker`, so nothing is downloaded), `init_db` and
  `seed_sample_data` on a private in-memory SQLite engine, `get_db`
  closing its session, company and metrics delete/404/500 responses,
  repository paths the HTTP API does not hit by itself, CORS origin
  parsing, `/api/v1/test-config`, and the placeholder
  `fetch-financial-metrics` route. 55 new tests. The previous suite was
  758.
- Decision, 80% gate: `.github/workflows/tests.yml` and the README test
  command add `--cov-fail-under=80`. pytest-cov fails the process when
  the TOTAL for `app`, `main`, and `scripts` is below 80. `--cov-branch`
  counts branches as well as statements. The table rounds TOTAL to a
  whole percent; the sentence under the table is the exact figure the
  gate uses.
- Decision, tests left as QA wrote them. The `get_db` tests use a small
  stand-in session so they can see that the real generator yields that
  object and calls `close()`, including when the caller raises. The
  repository tests inject `IntegrityError` because SQLite's message does
  not contain the constraint name `uq_company_name_ticker`; they assert
  the `ValueError` (or the re-raised `IntegrityError`) and that
  `rollback` ran. The 500 tests inject a repository failure and assert
  the HTTP body, including that a password in the exception text is not
  returned. Those doubles drive a real branch. They are not assertions
  that a mock was configured.
- Company-shaped pins, left in place for the later instrument model
  (GPW/US/EU stocks plus ETFs/ETCs). Each one matches today's code.
  - `test_yahoo_finance_collector.py::test_company_info_maps_provider_fields`
    pins the mapped company keys and the fixture name `Apple Inc.`.
    Needed today. Extra keys would still pass.
  - `test_company_info_falls_back_to_short_name_and_usd` pins the
    `shortName` fallback and default currency `USD`. Needed today.
  - `test_financial_statements_return_all_six_frames` pins the exact set
    of six statement keys. Needed today. A new key would fail it.
  - `test_key_metrics_map_ratios_from_provider_info` pins the ratio keys
    the collector copies. It does not assert `debt_to_assets` (open
    issue #21). Needed today for the keys it lists.
  - `test_init_db.py::test_init_db_creates_tables_on_configured_engine`
    requires tables `companies` and `financial_metrics` to exist. It is
    a subset check. Needed today.
  - `test_seed_sample_data_inserts_companies_and_apple_metrics` requires
    the exact ticker list `AAPL`, `MSFT`, `TSLA` and two annual Apple
    metrics for 2022 and 2023. Needed today; this is the seed catalog.
  - `test_seed_sample_data_runs_once` requires 3 companies and 2 metrics.
    Needed today.
  - `test_delete_and_not_found_api.py` 404 tests require the detail
    `Company not found`. Needed today.
  - `test_delete_company_keeps_other_companies` requires the remaining
    ticker list `[KEEP]`. Needed today for that one-row case.
  - `test_create_company_business_error_returns_400` requires the detail
    `Company name or ticker already exists`, which the test raises
    itself. Needed today as a pass-through. It does not cover a real
    duplicate insert (open issue #16).
  - `test_data_collection_wiring.py::test_fetch_financial_metrics_is_a_documented_placeholder`
    requires the placeholder body and ticker `AAPL`, which is the
    request it sends. Needed today.
  - `test_repository_edge_paths.py::test_company_create_maps_named_constraint_to_value_error`
    requires `uq_company_name_ticker` in the error text. Needed today.
  - `test_company_is_unique_checks_name_or_ticker` requires uniqueness on
    name or ticker. Needed today.
- PR #13 is merged as `a10e196`. PR #15 is merged as `b2541d7`.
  PR #14 is merged as `db0cc12`. PR #22 is merged as `778735e`.
- Reviewer nits from PRs #14 and #15 (`persist-credentials: false`,
  isort `known_first_party`, README lint wording) are not in this
  change. They are a separate branch off master.
- Verification, from the repository root, no `.env` file, in a network
  namespace whose connect to `1.1.1.1:443` failed. Python 3.12.3,
  pytest 7.4.3, packages from `requirements.txt`. Command:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -W error::DeprecationWarning --cov=app --cov=main --cov=scripts --cov-branch --cov-report=term-missing --cov-fail-under=80`
  - This branch: `813 passed in 11.89s`, no warnings summary, TOTAL
    `92%`, exact total `91.77%`.
  - Same command on `b2541d7` (master, without these tests): `758 passed
    in 10.73s`, TOTAL `76%`, exact total `76.08%`, gate failed. That is
    the point of the threshold.
  - Random order seeds 7, 21, and 42, same flags: `813 passed` each,
    exact total `91.77%`, no warnings summary.
  - Each new test file collected and passed in its own process.
  - An open audit saw no read or write of a `.env` inside the
    repository. One existing test writes a `.env` under
    `/tmp/pytest-of-ubuntu/...` and reads that temporary file. pytest-cov
    writes a gitignored `.coverage` data file in the repo root; it was
    deleted and is not part of the commit. No `__pycache__` was written
    while `PYTHONDONTWRITEBYTECODE=1`.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
  Account usage was not available in this session; no percentage recorded.
- The next-action line that named Alembic and PostgreSQL (#8, #9, #10)
  as the next work was the order when this entry was written. The live
  next action is the product-requirements entry at the top of this
  journal.
- Published as [PR #22](https://github.com/Waber/Investment-AI-Companion/pull/22),
  merged as `778735e`.

## 2026-10-07 - Tooling configuration

- Scope: configuration and docs only. Black line length 79 with target
  Python 3.12, isort profile `black` at line length 79, flake8 max line
  length 79, and pytest `testpaths` plus a registered `integration` marker.
  No `.py` files edited. No new tools, dependency changes, or CI.
  Rebased onto `origin/master` `db0cc12` after PR #14 (minimal CI) was
  rebase-merged. The CI entry is next, then the deprecation entries.
  Both are kept. CI's `-W error::DeprecationWarning` and
  `-p no:cacheprovider` still apply: this config sets neither
  `filterwarnings` nor a cache plugin. With those flags and the coverage
  report, local `pytest -q` is 758 passed, no warnings summary, coverage
  total 76%. `addopts` `-m "not integration"` does not drop any current test.
- Why a separate `.flake8`: Black, isort, and pytest read `pyproject.toml`.
  flake8 does not. It only looks at `setup.cfg`, `tox.ini`, and `.flake8`.
  flake8 6 already defaults to 79 columns, so a no-flag `flake8` run is 79
  even without this file. `.flake8` records that 79 in a file flake8 reads.
  Black is the tool whose default (88) changes results unless
  `line-length = 79` is set.
- Decision, `--strict-markers`: adopted, in pytest `addopts`. An unregistered
  marker is a collection error instead of a warning the run can still pass.
  Checked with a throwaway test using `not_a_registered_marker`: collection
  stopped with that name not found in `markers`. The suite uses
  pytest-asyncio's registered `asyncio` marker and built-in `parametrize`
  only, including `tests/test_model_config_compatibility.py`. A misspelled
  `integration` marker cannot silently join the SQLite suite.
- Decision, default selection: `addopts` also passes `-m "not integration"`.
  A test marked `integration` is deselected unless the command line passes
  `-m integration` (that later `-m` replaces the addopts expression). A
  throwaway marked test was deselected by `pytest -q` and ran only with
  `-m integration`. There are no integration tests in the tree yet.
- Decision, flake8 `extend-ignore`: not set. flake8 6 already ignores W503
  and W504. E203 does not occur on the files that pass Black at 79 columns.
  No per-file ignores.
- Decision, pytest config boundary: `pyproject.toml` does not declare a
  pytest version, dependencies, or `filterwarnings`. pytest-asyncio 0.21.1
  breaks on pytest 8 or later, so versions stay in `requirements.txt`.
  `filterwarnings = error` is a pending decision and is not set here.
- Files checked with `black --check`, `isort --check-only`, and `flake8`
  and no extra flags. Results match `black --check --line-length 79`,
  default isort, and default flake8 on the same files, including isort
  `--profile black --line-length 79`. Pass means exit 0. Not reformatted.
  - Pass all three: `main.py`, `app/core/validation.py`,
    `tests/test_lifespan_cors.py`, `tests/test_validation_errors.py`,
    `tests/test_collection_updates.py`,
    `tests/test_metric_creation_conflicts.py`,
    `tests/test_financial_metric_updates.py`,
    `tests/test_model_config_compatibility.py`.
  - `tests/test_company_update_conflicts.py`: Black and flake8 pass. isort
    fails because `sqlalchemy.exc` is imported after the application
    imports. The black profile asks for the same move as default isort.
  - Production files from the deprecation cleanup, same before and after
    this config: isort passes `app/core/database.py`, `app/models/company.py`,
    `app/models/financial_metrics.py`, and `app/models/historical_data.py`.
    isort fails `app/api/data_collection.py`. Black 79 and flake8 still fail
    all five for pre-existing debt.
- `python3 -m isort --check-only .` with this profile fails 12 files, not
  only the cleanup files. None were reformatted. The list is
  `alembic/env.py`, `setup_database.py`, `app/api/companies.py`,
  `app/api/data_collection.py`, `app/api/financial_metrics.py`,
  `app/core/config.py`, `app/core/init_db.py`,
  `app/data_collectors/yahoo_finance.py`, `app/models/database_models.py`,
  `app/repositories/company_repository.py`,
  `app/repositories/financial_metrics_repository.py`, and
  `tests/test_company_update_conflicts.py`.
  `black --check tests` leaves 19 files unchanged and `flake8 tests`
  passes. `isort --check-only tests` fails only
  `tests/test_company_update_conflicts.py`. README lint commands now
  include `tests`.
- Default Black (88 columns) would reformat `main.py` and
  `tests/test_lifespan_cors.py`. Configured 79 leaves both unchanged.
- Verification, from the repository root, no `.env` (only `.env.example`):
  - Before this config, on `origin/master` `a10e196`:
    `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q` -> 758 passed, no
    warnings summary. `python3 -m pytest --collect-only -q` -> 758 collected.
  - After this config: the same command -> 758 passed in 9.34s, no warnings
    summary. `python3 -m pytest --collect-only -q` -> 758 collected.
    `python3 -m pytest --markers` lists `integration`.
  - This environment has no project `.venv`. The interpreter was Python 3.12
    with the pinned Black 23.11.0, isort 5.12.0, flake8 6.1.0, and
    pytest 7.4.3 from `requirements.txt`. README lint commands were run the
    same way via `python3 -m` and read the new config. `app/` and
    `setup_database.py` still fail those checks because of older debt.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
  Account usage was not available in this session; no percentage recorded.
- Published as [PR #15](https://github.com/Waber/Investment-AI-Companion/pull/15),
  merged as `b2541d7`.

## 2026-10-07 - Minimal pytest CI

- Scope: one GitHub Actions workflow for the existing SQLite pytest suite
  (issue #5). No lint gate, Postgres, Docker, dependency changes,
  or `pyproject.toml`. Coverage is reported and does not fail the job.
- Decision: `.github/workflows/tests.yml` on `pull_request` and `push` to
  `master`. Python 3.12, `python -m pip install -r requirements.txt` with
  the setup-python pip cache, `PYTHONDONTWRITEBYTECODE=1`, the job fails if
  `.env` exists, and the workflow does not read GitHub Actions secrets.
  Command adds a coverage report and does not write JUnit XML.
  PR #13 is rebase-merged, so the command now includes
  `-W error::DeprecationWarning`.
- The draft QA spec is applied. Pending Raul: the coverage threshold
  (`--cov-fail-under=70`), JUnit XML, and the `MIN_TESTS` gate.
- PR #14 is merged into master as `db0cc12`. Local Python 3.12.3 with
  no `.env`: `758 passed in 13.56s`, no warnings summary, coverage total
  `76%`.
  Negative check: commit `806faef` failed on purpose
  (https://github.com/Waber/Investment-AI-Companion/actions/runs/37681557386,
  `1 failed, 742 passed, 4 warnings`) and was dropped before merge.
- Verification: with `-W error::DeprecationWarning` and the coverage report,
  the suite is `758 passed`, 0 warnings, and `76%` coverage. GitHub Actions
  run 37682560920 is green:
  https://github.com/Waber/Investment-AI-Companion/actions/runs/37682560920
  Job log: `758 passed in 13.67s` and `TOTAL ... 76%`.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
- Delivery: [PR #14](https://github.com/Waber/Investment-AI-Companion/pull/14)
  on `cursor/minimal-pytest-ci-ed2f`. PR #14 is merged into master as
  `db0cc12`.

## 2026-10-07 - QA nits on the deprecation cleanup

- QA approved [PR #13](https://github.com/Waber/Investment-AI-Companion/pull/13)
  at `b05c79a` with three non-blocking notes. Fixed on
  `cursor/deprecation-cleanup-7154`. PR #13 is merged as `a10e196`.
- `docs/work-state.md` now says issue #5 and issue #6. Those numbers are
  GitHub issues, not pull requests. The pull request body matches.
- The suite command in the cleanup entry below is the portable form, run
  from the repository root: `.venv/bin/python -m pytest -q -p no:cacheprovider`.
- Code review of `330c1bd` asked to stop writing `.env` into the repo.
  The warning check still starts in a temporary directory with a minimal
  environment. The child asserts that its working directory is not the
  project root. `Settings` reads `.env` from that directory, so a repo-root
  `.env` is not loaded. The test does not write any file into the repo.
  `PYTHONPATH` still points at the repo.
- RED, with the pre-cleanup sources restored and this test kept: the check
  failed. The child raised `MovedIn20Warning` from `declarative_base()` in
  `app/core/database.py`.
- Full suite on the current sources: `758 passed in 6.39s`, no warnings
  summary. The targeted warning check is included.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
- PR #13 is merged as `a10e196`.

## 2026-10-07 - Pydantic and SQLAlchemy deprecation cleanup

- Scope: remove project-owned deprecated configuration without changing
  validation, ORM conversion, response fields, or OpenAPI examples.
  Tracked as GitHub issue #4. Branch `cursor/deprecation-cleanup-7154`,
  based on `origin/master` `a58dc8a`. No dependency upgrade, migration,
  schema redesign, live provider call, or private `.env`.
- Why this shape, for learning: Pydantic v1 stored model options in a nested
  `class Config`. Pydantic 2.6 still accepts that nested class, but warns and
  will remove it in v3. `model_config = ConfigDict(...)` is the same map of
  options, declared directly on the class. `from_attributes=True` is what
  lets `model_validate` read a SQLAlchemy row (or any object with attributes)
  instead of only a dict. Financial metrics already set
  `allow_inf_nan=False` on the shared base model. The response model sets
  that flag again next to `from_attributes=True`, so replacing the nested
  `Config` class cannot drop the Infinity/NaN ban. Pydantic 2.6 merges a
  subclass `model_config` with its parent; setting the flag explicitly does
  not rely on that merge. `FetchCompanyRequest` keeps
  `json_schema_extra={"example": {"ticker": "AAPL"}}`, which is the example
  FastAPI copies into the OpenAPI component. SQLAlchemy 2 moved
  `declarative_base` to `sqlalchemy.orm`. The function still builds one
  shared `Base`; only the import path changed. `CompanyDB` and
  `FinancialMetricsDB` still use that same `Base.metadata`.
- Decisions: do not reformat untouched legacy lines. `class Config` remains
  only where it existed. Create and update metric models stay without
  `from_attributes`. Historical prices still have no SQLAlchemy model; the
  new test uses a plain attribute object for that schema. The warning check
  runs in a fresh interpreter and turns the two targeted messages into
  errors. It does not ignore warnings.
- RED, before any production edit: `tests/test_model_config_compatibility.py::test_project_imports_do_not_emit_targeted_deprecations`
  failed. The child process raised `sqlalchemy.exc.MovedIn20Warning` at
  `app/core/database.py` while importing `declarative_base` from
  `sqlalchemy.ext.declarative`. A separate import of the five modules, with
  warnings recorded, showed five warnings: that SQLAlchemy warning plus four
  `PydanticDeprecatedSince20` warnings (`company`, `financial_metrics`,
  `historical_data`, `data_collection`). The normal suite showed four because
  it did not import `historical_data`. The other new behavior tests passed
  against the old code.
- GREEN: the warning check passes, and importing those five modules records
  zero warnings. Focused file plus JSON-overflow, lifespan/CORS, financial
  metric validation, and data-collection tests: 580 passed before the final
  unused-import cleanup. Final full suite is below.
- Baseline, clean environment, no `.env`, pinned requirements
  (`pydantic==2.6.1`, `sqlalchemy==2.0.23`), Python 3.12.3:
  `742 passed, 4 warnings in 5.67s`.
- Final full suite: `758 passed in 6.50s` before the pre-PR rebase, and
  `758 passed in 6.74s` after `git fetch` and `git rebase origin/master`.
  The branch was already on `a58dc8a`, so the rebase did not change files.
  Pytest printed no warnings summary either time. Sixteen new tests.
- Command, from the repository root:
  `.venv/bin/python -m pytest -q -p no:cacheprovider`
- Style: `black --check --line-length 79`, `isort --check-only`, and
  `flake8` pass for `tests/test_model_config_compatibility.py`. `isort`
  passes for `app/core/database.py`, `app/models/company.py`,
  `app/models/financial_metrics.py`, and `app/models/historical_data.py`.
  `isort` still fails `app/api/data_collection.py` for pre-existing import
  order. `black --line-length 79` still wants to reformat the five production
  files, and `flake8` still reports pre-existing long lines, whitespace, and
  unused imports on those files. None of the new lines are in that flake8
  list. `git diff --check` is clean. Repo-wide lint was not run. Full-file
  reformatting was skipped because it would rewrite untouched lines.
- Status corrections kept alongside the older entries below: PR #2
  (`fix/startup-lifespan-cors`) is merged as `b10d06e`. PR #3 (rebase
  workflow) is rebase-merged as `a58dc8a`. Sentences below that still say
  those pull requests were open are the record of that moment, not the
  current state.
- AI model: Grok 4.7 (Cursor cloud agent). Wall clock started about
  19:49 UTC; elapsed time was not stopwatch-measured. Account usage was not
  available in this Cursor session; no percentage was recorded and no reset
  was redeemed.
- Published as [PR #13](https://github.com/Waber/Investment-AI-Companion/pull/13),
  merged as `a10e196`.
- After that delivery: guarded Alembic baseline and isolated PostgreSQL
  tests. Issues #5 (minimal CI) and #6 (tooling config) are separate and
  do not own this journal or `docs/work-state.md`. PR #15 is merged as
  `b2541d7`. PR #22 is merged as `778735e`.

## 2026-10-07 - Rebase workflow rule

- Scope: documentation only. Record that this project keeps a linear history
  with rebase. No production code, tests, or GitHub repository settings.
- Decision: add a dedicated `## Git Workflow` section to AGENTS.md, after
  Working Agreements. Feature branches rebase onto `origin/master`
  (`git fetch`, then `git rebase origin/master`). Pulls use `git pull --rebase`.
  Own unpublished or feature-branch commits may be tidied with interactive
  rebase before a pull request. After rebasing an already-pushed feature
  branch, push only with `--force-with-lease`, and only on that author's own
  feature branch. Never rewrite `master` or shared branches. Pull requests
  are integrated with GitHub "Rebase and merge". That option is enforceable
  only when the repository has "Allow rebase merging" enabled; changing
  repository settings is the user's decision, not an agent's. Agents still
  must not merge a pull request unless the user explicitly authorizes it.
  `git config pull.rebase true` in this repository makes later pulls rebase.
  On a branch someone else also pushes to, coordinate before rebasing, or
  rebase only right before merge. Rebase conflicts are resolved by preserving
  both sides' intent, then the relevant tests are rerun; if unsure, stop and
  report.
- Why, for learning: a straight line of commits is easier to read, bisect,
  and review than merge-commit knots.
- Verification: reviewed the documentation diff. Pytest was not run because
  no code behavior changed. Account usage from the previous ChatGPT tooling
  was not available in this Cursor session; no usage percentage was recorded.
- AI model: Grok 4.7 (Cursor cloud agent). Elapsed time was not measured.
- Delivery: one commit on `cursor/rebase-workflow-rule-0803`, based on
  `origin/master` (`b10d06e`, merge of pull request #2). Pull request opened
  against `master` and left unmerged. Deprecation cleanup is in progress on
  a separate Developer branch. This pull request and that one both edit the
  top of the journal and work-state; whichever merges second rebases and
  resolves those conflicts carefully.
- Update: PR #3 was rebase-merged as `a58dc8a` on 2026-10-07. The deprecation
  cleanup entry above is the later edit to these docs.

## Next Iteration Handoff - 2026-10-07

Status update: PR #2 is merged as `b10d06e`. PR #3 is rebase-merged as
`a58dc8a`. The deprecation cleanup this handoff describes is implemented on
`cursor/deprecation-cleanup-7154`
([PR #13](https://github.com/Waber/Investment-AI-Companion/pull/13));
see the 2026-10-07 cleanup entry above.
The bullets below stay as the original handoff.

### Resume Here

- User requested documentation only for this handoff. Do not treat it as an
  instruction to start implementation now. PR #2 is open against master:
  https://github.com/Waber/Investment-AI-Companion/pull/2
- Delivered branch: `fix/startup-lifespan-cors`, last implementation `5bd286c`,
  publication checkpoint `4fa939d`. This documentation commit follows both.
- Primary repository: `/Users/przemkowy/IdeaProjects/Investment-AI-Companion`.
  Current worktree: `/private/tmp/investment-metric-updates`. The configured
  PycharmProjects directory is not the authoritative repository. Temporary
  worktrees may disappear; recover committed work from Git, not stale paths.
- Read AGENTS.md and docs/work-state.md, inspect status/worktrees, fetch origin
  and check PR #2 before editing. If merged, branch from updated origin/master.
  If still open, use an explicit dependent branch from its current head and
  document the dependency; do not assume master contains these changes.
- Preserve user changes and the primary checkout's untracked `.python-version`.
  Do not assume any historical demo server/database remains available.
- No agents or implementation tasks remain active. Stop reason: user chose to
  defer further implementation and requested a reusable handoff, not exhaustion.
  Last checked usage before handoff: 42% five-hour / 7% weekly. Recheck live usage
  on resume; default checkpoint threshold is 80% unless explicitly overridden.

### Next Bounded Task: Deprecation Cleanup

Goal: remove project-owned Pydantic/SQLAlchemy deprecated configuration/imports
without changing validation, ORM conversion, response fields or OpenAPI examples.
Use a dedicated branch, a developer agent and an independent reviewer.

Files to inspect (do not mechanically replace configuration without tests):
- `app/core/database.py`: import declarative_base from sqlalchemy.orm; preserve
  the shared Base, engine and session behavior.
- `app/models/company.py`, `app/models/financial_metrics.py`,
  `app/models/historical_data.py`: migrate class Config to ConfigDict while
  retaining from_attributes. Financial metrics already inherits
  ConfigDict(allow_inf_nan=False); preserve that restriction when adding config.
- `app/api/data_collection.py`: migrate FetchCompanyRequest's json_schema_extra
  and retain its ticker example in generated schema.

Execution and acceptance:
1. Establish the full-suite baseline: last verified 742 passed, four warnings.
   Explicitly import historical_data in focused tests; it may not be loaded by
   the normal app suite, so four warnings are not an exhaustive file count.
2. Add regression coverage for model_validate on attribute/ORM objects, response
   serialization, rejection of nonfinite metrics and schema example preservation.
   Add a warning-as-error check for the targeted deprecations and demonstrate
   failure before migration. Do not suppress warnings to make tests pass.
3. Apply only minimal configuration/import changes; no dependency upgrades,
   migrations, schema redesign, provider calls or unrelated formatting.
4. Run focused tests, full suite, targeted warning checks and scoped style checks.
   Existing JSON-overflow, lifespan and CORS regressions must remain green.
5. Independent review, fix findings, then commit and update this journal and
   work-state with actual results, remaining warnings, branch and next action.
   Confirm publication scope with the next user instruction; this handoff only
   authorizes adding documentation to the existing PR.

Known test command (run from `/private/tmp`, replace worktree path if changed):
```bash
/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/private/tmp/investment-metric-updates \
  /Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python \
  -m pytest -q -p no:cacheprovider /private/tmp/investment-metric-updates/tests
```
This avoids loading private .env configuration. Verify the interpreter still
exists. Run style checks from the worktree, not /tmp; the previous scoped checks
used Black with explicit --line-length 79, isort and flake8. Do not claim default
Black or repository-wide lint passed unless actually verified.

### Subsequent Backlog

After the small cleanup: guarded Alembic baseline/adoption and automated isolated
PostgreSQL tests, then editable investor profiles, then source-aware AI analysis.
Use the September research-workflow plan/spec for requirements, but reconcile its
old checkboxes with current code and this journal. CRUD/collector regressions,
JSON-safe overflow errors and lifespan/CORS are already delivered in PR #2.
Never merge the historical dependency WIP blindly: its OpenAI pin conflicted
with the FastAPI dependency set. Financial-metrics ingestion remains a placeholder.

## 2026-10-07 - Lifespan, CORS And Publication

- Dedicated branch `fix/startup-lifespan-cors` in the existing isolated worktree.
  User requested completion, push and PR; no merge. Includes five unpublished
  ancestor commits from the October 4 regression/validation work.
- Kierkegaard implemented lifespan using existing `init_db()`, propagation of
  initialization failures, disabled initialization mode and exact CORS matching
  without the URL-added root slash. No new database creation path or migrations.
- RED: 7 failed / 18 passed before implementation. GREEN: 25 focused cases;
  coordinator full isolated suite 742 passed with four preexisting warnings
  (SQLAlchemy and Pydantic). Deprecated FastAPI startup warnings are gone.
- Full command from `/private/tmp`: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/investment-metric-updates /Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider /private/tmp/investment-metric-updates/tests`.
- Scoped checks: `black --check --line-length 79 main.py tests/test_lifespan_cors.py`,
  `isort --check-only` and `flake8` on the same files, plus `git diff --check`.
  Black's default 88-column check differs; explicit 79 matches default flake8.
- Updated IDE startup guide and stale remaining-work items. No user database,
  live provider, dependency upgrade or service restart. Migration/PG integration,
  profiles, AI and remaining deprecations deferred.
- Carver independently approved code/tests and the ancestor integration scan;
  reviewer reran 25 focused cases. Stop at completed scope, not quota. Commit,
  push and PR follow verification; no merge. Usage 6% at start, 29% after implementation.
  Agent model inherited; precise model identifier and elapsed time not measured.
- Published implementation `5bd286c` and prior slices in
  [PR #2](https://github.com/Waber/Investment-AI-Companion/pull/2) targeting master.
  No merge; agents closed. Final account usage 40% five-hour / 6% weekly.

## 2026-10-04 - JSON overflow validation fix

- Started from `2374acf` at50% five-hour/8% weekly usage. Dedicated branch
  `fix/json-overflow-validation`; bounded part of approved Task1, not full hardening.
- Plan: failing raw-overflow POST/PUT tests, minimal JSON-safe422 handler preserving
  ordinary error structure, persistence checks, full tests and independent review.
- Developer owns new validation module/tests and minimal main registration;
  coordinator owns documentation. No live calls, migrations or dependency changes.
- Faraday RED evidence:5 failed/4 passed, including four raw overflow500 responses
  and a nested nonfinite serialization failure. GREEN9 focused passed; coordinator
  independently ran full717 passed with six existing warnings using the clean-env
  command from prior entries. New-file Black/isort/flake8 checks passed.
- Nash approved independent spec/quality review and ran9 focused tests. Ordinary
  error detail structure remains unchanged; nonfinite float values become strings
  after jsonable encoding. No request body added to error responses. Main changes
  limited to registering the handler; no broad legacy formatting.
- Both agents closed at commit. Final review usage77% (below session90% ceiling).
  Stop at three completed slices with checkpoint buffer; do not start lifecycle
  work now. No push/merge or reset redemption. Inherited model, effort not timed.

## 2026-10-04 - Fake collector refresh regressions

- Separate branch `test/collector-refresh-regressions` based on reviewed `d9e56ce`.
  Developer owns only `tests/test_collection_updates.py`; no live provider calls.
- Scope: existing-company refresh, identity preservation, repeat without duplicates,
  missing provider result404 without writes, unrelated company/metrics preservation.
  Coordinator handles full tests/docs, followed by independent spec/quality review.
- Cicero delivered6 cases; coordinator full708 passed/six legacy warnings and
  scoped Black/isort/flake8 passed. Epicurus approved spec/quality without findings.
  No production changes or live provider calls. Both agents closed at commit.
  Characterization completes the planned collector refresh/not-found coverage.

## 2026-10-04 - Resume after user reset: metric creation conflicts

- User performed reset (coordinator did not redeem credit), usage0% both windows.
  Session-specific limit90%; AGENTS now permits an explicit session override.
- Branch `test/metric-creation-conflicts`, base `0008b0c`. Helmholtz owns a bounded
  test file: duplicate tuple rejection, each key component distinguishing records,
  real FK/unique constraint rollback with same-session reuse and persisted state.
- No production edits planned; characterize correct behavior. Coordinator owns
  continuity/full verification; independent review before commit. Collector follows
  as a separately committed slice if usage permits. Inherited model, time not timed.
- Results:6 new cases passed against unchanged production code. Full702 passed,
  six existing warnings, using prior clean-env pytest command. Poincare approved
  spec/quality with no findings. Black/flake8 passed; coordinator worktree-local
  isort found grouping drift from developer's temporary CWD check and corrected it.
  Usage20% five-hour/3% weekly; commit before starting collector work.

## 2026-10-04 - Company update conflicts and rollback

- Continued at60% five-hour usage with a small characterization slice on
  `test/company-update-conflicts`, based on `569a89e`. Same isolated worktree.
- Kant owns only the new conflict tests. Scope: duplicate name/ticker API
  rejection without mutation, then successful update; real constraint failure
  and recovery using the SAME repository session. No collector/metrics expansion.
- Coordinator will run full tests and independent review before local commit.
  At80% stop and notify user; no automatic reset. Inherited model, effort not timed.
- Completed3 characterization cases without production changes; coordinator full
  isolated pytest run696 passed, six existing warnings. Same env-i command as
  metric slice. Kant reports scoped Black/isort/flake8 passed; Raman static review
  approved specification/quality with no findings. No live database/provider calls.
- Usage rose60% ->75% ->82% between checks. Stop reason: user80% threshold reached;
  save local checkpoint and wait for explicit continuation, no reset redeemed.
  Agents closed. Next scope: metrics creation conflicts/rollback, then collector.

## 2026-10-04 - Financial metric update characterization

- User confirmed PR1 merged and authorized continuation with an80% account-usage
  stop threshold. Recorded this policy in AGENTS; no reset may be redeemed without
  authorization. Start usage29% five-hour/4% weekly consumed.
- New branch `test/financial-metric-updates`, base `1e05ab1`, worktree
  `/private/tmp/investment-metric-updates`. Primary checkout/user files untouched.
- Hubble owns only new update tests; coordinator handles docs and full verification;
  independent reviewer follows. Scope: partial updates/null/zero/omission and invalid
  updates, not all remaining Task2 work. Existing correct code need not change.
- Inherited agent model; exact model identity and elapsed effort not measured.
- Results:82 new API characterization cases across all20 numeric fields. All pass
  against existing production code; no newly reproduced/fixed defect is claimed.
  Tests compare PUT/GET, fresh persisted snapshots, identity and unrelated rows;
  rejected422 payloads preserve timestamps as well as values.
- Coordinator full suite:693 passed, six existing warnings. Command from
  `/private/tmp`: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/investment-metric-updates /Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider /private/tmp/investment-metric-updates/tests`.
- Black/isort/flake8 checks passed for the new test file. Independent Aristotle
  review approved spec compliance and quality without actionable findings.
- Hubble and Aristotle closed at delivery. Verification usage50% five-hour/8%
  weekly consumed; no reset. Stop at completed bounded scope, not exhaustion.
  Local commit only; remaining Task2 uniqueness/rollback/collector work not complete.

## 2026-10-04 - Recover and publish recent work

- User requested commit, push and PR. Recovered committed fixture/API/test work
  from `69258b9` onto `docs/demo-and-ide-delivery` in a new temporary worktree.
- Previous IDE documentation agents hit the usage limit before commit/review.
  The old temporary worktree now contains no files. Reconstructed the guide;
  do not describe it as an exact recovery of the uncommitted file.
- README links the guide. Current-state notes distinguish historical runtime
  observations from the present, unverified service state.
- No production behavior, dependency, database or primary-checkout changes.
  GUI startup and fresh installation remain untested. Verification and review
  results will be recorded before publication. No merge requested.
- Model inherited from session; exact identity and elapsed effort not measured.
- Verification: full isolated pytest suite passed611 cases with six existing
  warnings; `git diff --check` passed. Independent reviewer Ptolemy approved
  reconstructed documentation without actionable findings. Review was read-only;
  no GUI/provisioning/live provider validation is claimed.
- Publication includes the prior unpublished ancestor commits (404 behavior,
  website-update tests, API demo, fixtures and planning docs), but excludes the
  separate dependency-conflict WIP branch. Latest usage12% five-hour/2% weekly
  consumed; no reset redeemed. Scope ends with push and PR, not merge.

`CONVERSATION.md` contains legacy project history. This journal is the forward-looking delivery log for new agentic development.

## 2026-07-04 - Iteration 1 (project guidance and baseline tests)

### Scope
- Add repository-level agent/developer guidance.
- Add baseline automated tests.
- Fix financial metrics schema alignment.
- Add test seams for local API work without live providers.

### Status
- Delivered.

### Verification
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` -> passed, 4 tests, 6 legacy warnings.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check tests` -> passed, 5 test files unchanged.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only tests` -> passed.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 tests` -> passed.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check app main.py setup_database.py tests` -> failed on legacy formatting debt in application files; this was already present in the pre-edit baseline. New tests were formatted separately and pass `black --check tests`.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only app main.py setup_database.py tests` -> failed on legacy import-order debt in application files; this was already present in the pre-edit baseline.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 app main.py setup_database.py tests` -> failed on legacy style/import issues in application files; `tests/` passes separately.

### AI model
- ChatGPT Codex (GPT-5).
- Subagents used: spec reviewer, plan reviewers, and a documentation implementation worker.

### Time tracking
- Task window: 2026-07-04 17:46-18:05 CEST, about 19 minutes for implementation and verification after plan approval.
- Team/subagents used: yes.
- Coordinator effort: about 19 minutes wall-clock in this implementation window, plus earlier spec/plan orchestration on this branch.
- Developer effort: documentation worker completed Task 1; remaining implementation was coordinated in-session with TDD checkpoints.
- Reviewer effort: one spec review and three plan review passes before implementation; final code review was pending at delivery and was completed on 2026-09-08 (see follow-up below).

### Notes
- `.python-version` existed before this iteration as an untracked local file and was left unmodified/uncommitted.
- Local `.venv` has `httpx 0.28.1` while `requirements.txt` pins `httpx==0.25.2`; tests use `httpx.ASGITransport` to avoid the incompatible legacy `TestClient` path in this environment.
- Full application lint/format cleanup should be handled as a separate technical-debt iteration to avoid mixing broad style churn with this baseline test/refactor slice.

## 2026-09-08 - Baseline review and corrective changes

### Scope and status
- Completed the independent senior engineer/architect review of the full baseline iteration, not only the latest documentation commit.
- Fixed all three actionable findings on dedicated branches and integrated the approved commits into `feature/project-guidance-and-baseline-tests`.
- Independent reviewer Noether accepted each fix. No reported blockers remain for this iteration.
- Full findings, evidence, and remaining limitations: [baseline review](reviews/2026-09-08-baseline-review.md).

### Changes
- Configuration: represent CORS origins as a JSON array in `.env.example`; add a smoke test that loads the actual template in an isolated environment.
- Financial metrics: reject non-finite values before persistence across all 20 numeric fields, preserving finite numbers, nulls, and omitted update fields.
- Test database: enable SQLite foreign keys on every physical connection before schema creation; test missing-company rejection, valid persistence, and replacement connections.

### Team and branches
- Coordinator: Codex (GPT-6), integration, independent verification, and documentation.
- Noether: senior engineer/architect, baseline review and independent review of each corrective change.
- Descartes: configuration fix on `fix/config-template-startup` (source commit `2c7fae8`).
- Linnaeus: database/QA fix on `fix/test-database-integrity` (source commit `00d346b`).
- Ohm: financial validation fix on `fix/finite-financial-metrics` (source commit `bc7c724`).
- Developers worked in separate worktrees; the database and validation fixes ran in parallel. Agents inherited the coordinator model.
- Integrated application commits: `5597a00`, `5f1b2fb`, and `719f691`. At review delivery these were on the development branch; subsequent publication is recorded below.

### Verification
- Combined suite at `719f691`: **537 passed, 6 existing deprecation warnings**. This includes parameterized unit cases and API regression tests, not 537 distinct workflows.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m black --check tests`: passed, 8 files unchanged.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m isort --check-only tests`: passed with default settings.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m flake8 tests`: passed with default settings.
- Each corrective code commit passed `git diff --cached --check` before commit.
- The combined suite ran from `/private/tmp` with a clean environment and the repository on `PYTHONPATH`, without reading the developer's `.env`. Exact command:

```bash
/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/przemkowy/IdeaProjects/Investment-AI-Companion /Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider /Users/przemkowy/IdeaProjects/Investment-AI-Companion/tests
```

- An earlier coordinator test launcher disabled dotenv loading globally and caused the template smoke test to fail. Removing that launcher override, without changing application code, produced the final result above.
- No live PostgreSQL instance or market-data providers were used. Full legacy application lint cleanup and dependency upgrades were not part of this follow-up.

### Time tracking and continuity
- Recorded local commit checkpoints (CEST): configuration at 20:16, database at 20:21, validation at 20:24 on 2026-09-08.
- Exact per-agent durations were not measured; no synthetic effort totals are reported.
- A usage-limit interruption stopped Ohm before final verification; work resumed from the existing files after the user reset the limit.
- The existing untracked `.python-version` was preserved.

### Publication after user approval
- On 2026-09-08 the user authorized committing, pushing, and merging the reviewed iteration into the default branch.
- Confirmed GitHub's default branch is `master`; fetching showed no divergent remote commits.
- Pushed `feature/project-guidance-and-baseline-tests`, then fast-forwarded local `master` through all 14 iteration commits to `08fc2fe` without conflicts.
- Re-ran the full isolated suite on `master`: **537 passed, 6 existing warnings**.
- Pushed `master` and independently confirmed the remote ref at `08fc2fe72fa6dce61b5856d36a120c6d99b52bc5`.
- This documentation-only follow-up records that completed publication; it does not change the tested application or test files.

## 2026-09-08 - Remaining-work iteration (in progress)

- User authorized continuing the remaining work listed in the baseline review.
- Created `feature/research-workflow-and-hardening` from published `master` at `6e1f2fc` in an isolated worktree.
- Added explicit session checkpoint rules and `docs/work-state.md` at the user's request, so later sessions can identify what is done, what is unfinished, and why work stopped.
- This is a documentation checkpoint while work continues, not a usage-limit stop. The current usage check did not indicate a reached limit.
- Product clarification received: horizon over ten years, broad markets including Poland/US/Europe/Asia, moderate-to-high risk, stocks/bonds/ETFs/ETCs, excluding direct derivatives such as futures/CFDs. The user requires an editable demo profile and support for different preferences, not hardcoded personal assumptions.
- Coordinator: Codex (GPT-6). No implementation agents dispatched for this new iteration yet. Precise elapsed time is not being measured; implementation and verification will be logged at delivery.
- No application or test files changed in this checkpoint. The previously published baseline passed 537 test cases; tests are not being represented as a new run for documentation-only changes.

## 2026-09-08 - WIP partial checkpoint: Task 2 CRUD regressions (paused)

### State and stop reason
- Worktree: `/private/tmp/investment-crud-regressions`.
- Branch: `fix/crud-update-regressions`; pre-checkpoint HEAD: `10ab10d6bf1ba15e9105dc85d86b32c1816a5835`.
- User-requested pause to preserve state before the next iteration after context/usage pressure. The user reports that the previous run encountered a usage-limit error and that credits have now been reset. No credit balance or reset result was independently checked in this task.
- Task 2 remains incomplete and paused. The checkpoint is not approval to resume implementation or integrate changes.

### Actual work and decisions
- Confirmed the requested worktree, branch, and base commit; located AGENTS, the approved plan/design, and relevant source/test paths.
- Read the workflow skills for TDD, systematic debugging, plan execution, and verification; read AGENTS and the existing journal for this checkpoint.
- No application or test edits were made. Neither `tests/test_updates_api.py` nor `tests/test_collection_updates.py` was created. The only checkpoint edit is this journal entry.
- No implementation/design decisions or behavior corrections have been established. No delegation, integration, push, or worktree deletion was performed.
- All commands launched by this task had exited; no owned implementation or testing process remained running.

### Verification actually performed
- `pwd`: confirmed `/private/tmp/investment-crud-regressions`.
- `git status --short --branch`: clean worktree on `fix/crud-update-regressions` before the journal edit.
- `git log -1 --format='%H %s'`: confirmed the pre-checkpoint HEAD above (`docs: clarify migration and analysis contracts`).
- `git diff --stat`, `git diff`, and `git diff --cached`: all empty before the journal edit.
- `git diff --check`: passed after adding this checkpoint entry.
- No pytest, red/green cycle, full suite, formatter, or linter was run. Earlier journal test results are historical, not verification of Task 2.

### Pending work, blockers, and exact next action
- The intentional user pause is the current stop condition; implementation blockers have not yet been investigated. Parent and Russell reviews remain pending before any final implementation commit or integration; the user separately authorized this WIP checkpoint commit.
- On explicit resumption, first inspect git status, read `docs/work-state.md`, the latest journal entry, `docs/superpowers/plans/2026-09-08-research-workflow-and-hardening.md` (Task 2), and `docs/superpowers/specs/2026-09-08-research-workflow-and-hardening-design.md`. Then inspect the assigned APIs/repositories, existing tests/conftest, and configuration without reading `.env` or a private database.
- Write the first failing regression test before production edits. Cover missing-update 404, company URL omitted/changed/null, metrics partial updates/null, conflicts, rollback/recovery, relevant cascade behavior, and fake-collector existing-company/404 paths. Investigate deterministic duplicate-ticker 400 semantics only as supported by regression evidence and existing constraints.
- Implementation ownership remains limited to `app/api/companies.py`, `app/api/financial_metrics.py`, `app/repositories/company_repository.py`, `app/repositories/financial_metrics_repository.py`, `tests/test_updates_api.py`, and `tests/test_collection_updates.py`. Do not edit data collection API, main, models, conftest, or unrelated files.
- Pending test invocation after confirming isolation: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 /Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider`, from this worktree. Use deterministic fakes, no live providers, no `.env`, and no private database. Record exact red/green and full-suite results when actually run.

### Model and time tracking
- Agent: Codex (GPT-6); no subagents used.
- Exact elapsed time was not measured. This entry records a partial checkpoint, not delivery of Task 2.

## 2026-09-22 - Missing-update responses (bounded iteration, completed locally)

### Scope and plan
- User authorized only the missing-record update fix, regression tests, independent review, a local commit, and journal. Other remaining-work tasks stay paused.
- Created `fix/missing-update-not-found` at `/private/tmp/investment-update-404` from CRUD checkpoint `83bb7ed`. Old temporary worktrees are absent, but commits remain in Git. No old registrations/branches removed.
- Both update routes raise intended HTTP 404 inside a broad exception handler that converts it to 500. Start with failing API regressions, apply the smallest fix, verify 400/500 and successful-update behavior remains intact.
- Carson implements two routes and focused tests. Coordinator handles baseline/final verification, usage checks, and documentation; separate review follows implementation.
- No migrations, dependency updates, profiles, broad formatting, push, or merge.

### Baseline and resource checks
- Fresh baseline: 537 passed, six existing warnings. Command, from `/private/tmp`:

```bash
/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/investment-update-404 /Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider /private/tmp/investment-update-404/tests
```

- Usage: before work, 8% five-hour and 2% weekly used; after preparation, 14% and 3%. These are not remaining-context measurements. No exact context counter is exposed; no reset/purchase performed.
- After implementation usage: 33% five-hour/6% weekly used; initial verification: 40%/7%; review and formatting completion: 48%/9%. These account-wide snapshots do not measure task cost or context capacity.
- Coordinator and agents use the configured inherited Codex model; exact model identity and elapsed effort were not independently measured in this iteration.

### Changes and verification
- Both update routes now re-raise HTTPException before the broad exception handlers. Missing company and financial-metrics updates preserve their existing 404 messages rather than returning 500. No repository/model/dependency changes.
- Added eight cases in `tests/test_missing_updates_api.py`: missing-record exact 404 and no DML/data changes, existing successful persisted updates, business errors mapped to 400, unexpected errors mapped to generic 500 without leaking their message.
- Carson reported RED: two tests failed with 500 instead of 404, six passed. After the fix, eight passed; full suite 545 passed. The coordinator did not independently reproduce RED.
- Hume independently reviewed specification compliance and code quality: approved, no actionable findings. His focused test run passed all eight cases.
- Coordinator's first style check found new-test formatting/import/line-length issues. Carson corrected only test formatting; no functional changes.
- Coordinator reran the full command above after formatting: **545 passed, six existing deprecation warnings**.
- Default checks passed for all nine test files: `.venv/bin/python -m black --check tests`, `-m isort --check-only tests`, `-m flake8 tests` (using the primary repository interpreter from this worktree).
- Tests use isolated SQLite, with repository exceptions injected only for error mapping. No live database/provider verification or application-wide lint cleanup was performed. Legacy warnings remain out of scope.

### Delivery and next action
- Carson and Hume were closed after final reports. No owned long-running process remains from this iteration.
- This change and documentation are saved together in a local commit on `fix/missing-update-not-found`; no push or merge. Primary `master` and the user's untracked `.python-version` remain unchanged.
- Stop reason: approved bounded scope completed, not resource exhaustion. No account reset or credit purchase was needed or performed.
- Next authorized iteration: integrate this reviewed fix as appropriate, then add failing Task 2 regressions for URL omission/change/null. Broader CRUD, lifecycle, PostgreSQL, profiles, and AI work remain unfinished; see [work-state](work-state.md).

## 2026-09-22 - Company website updates (bounded test-only task, completed locally)

- User authorized the next small task with resource checks; scope is only website omission, replacement, null clearing, and invalid URL rejection. No broader CRUD/migration/AI work.
- Branch `test/company-website-updates` at `/private/tmp/investment-website-updates`, based on reviewed `3a2b0af`; parent suite verified in this session: 545 passed, six legacy warnings.
- Existing update code already handles `exclude_unset` and optional URL serialization. Contrary to the earlier generic next-step wording, characterization tests can legitimately pass immediately; do not invent a failing bug or change correct production behavior.
- Ohm owns only `tests/test_company_website_updates.py`; coordinator owns documentation and final verification. Separate independent review follows.
- Initial resource check: 59% five-hour and 10% weekly used. These account-wide percentages are not a context measurement or a completion guarantee. No reset/purchase.
- No push/merge; preserve prior branches and the primary checkout's unrelated `.python-version`.

### Results and handoff
- Added only `tests/test_company_website_updates.py` plus coordinator documentation. Four cases verify omission, normalized replacement, null clearing, and invalid URL rejection without mutation through PUT responses, GET readback, and fresh database sessions. Production code was already correct and remains unchanged.
- Ohm reported focused four passed/full 549 passed, six existing warnings. Dalton independently approved spec and quality, no findings, and ran all four focused cases successfully.
- Coordinator independently ran the full suite: 549 passed, six existing warnings. Command from `/private/tmp`: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/investment-website-updates /Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider /private/tmp/investment-website-updates/tests`.
- Coordinator's repository-local isort check required one blank line between third-party and application imports despite the developer's reported pass; corrected that formatting-only issue after review. Default Black/isort/flake8 checks and the suite are rerun before commit.
- Usage after preparation: 65% five-hour/11% weekly used; after implementation and full verification: 78%/13%. No exact context counter, reset, or purchase. Stop at completed scope to conserve the remaining allowance, not because a limit was reached.
- Agents Ohm and Dalton closed at delivery. Same configured inherited model; exact identity and elapsed effort not independently measured. No agent-owned long-running process.
- SQLite-only characterization; no PostgreSQL/provider calls and no claim of fixing a newly reproduced bug. Existing warnings remain.
- Next separately authorized slice: metric partial-update/null regression coverage. The full Task 2 remains incomplete. Keep this local branch for later integration; no automatic push/merge.
- Final post-format verification: 549 passed, six existing warnings; default Black/isort/flake8 passed for all ten test files. After review and final verification, usage was 85% five-hour/14% weekly consumed. Scope completed with remaining allowance; both agent shutdowns confirmed.

## 2026-09-26 - Local API demo and request guide

- User approved running the latest tested backend with an isolated database and documenting API requests. Worktree `/private/tmp/investment-api-demo`, branch `chore/local-api-demo`, base `731c513`. No production behavior/dependency changes or merge/push.
- Design: reuse installed Python environment and existing app; fresh owner-only PostgreSQL cluster, Unix socket only, loopback HTTP, synthetic data. Avoid real `.env`, API credentials and developer database. Provide a curl walkthrough and repeatable HTTP smoke client; review them independently.
- Coordinator initialized PostgreSQL14.19 at `/private/tmp/iac-demo.h7TbGw/data`, role `demo`, DB `investment_demo`, socket directory `/private/tmp/iac-demo.h7TbGw`, port15432, host authentication rejected and TCP listening disabled.
- API runs detached on `127.0.0.1:8081` with clean environment and DEBUG=False. Logs/PID reside in the runtime directory; these intentionally running services remain available to the user. Temporary files are not durable storage or backups.
- Verified startup schema creation, company POST and financial-metrics POST on PostgreSQL, Swagger HTML200, and diagnostic endpoint403. Seeded one synthetic `DEMO` company and one metrics row (IDs1 initially); no external providers called.
- Fresh isolated regression suite: 549 passed, six existing deprecation warnings. Command from `/private/tmp`: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/investment-api-demo /Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider /private/tmp/investment-api-demo/tests`.
- Curie develops only `docs/api-demo.md` and `scripts/smoke_demo.py`; coordinator owns runtime, README and state/journal. Independent review and final live smoke results follow below.
- Initial usage60% five-hour/26% weekly; after launch73%/28%. No context-capacity inference, reset or purchase. Exact agent model/effort duration not independently measured.
- This manually tested local PostgreSQL runtime does not replace the remaining automated migration/integration-test work. AI/profile functionality remains unimplemented; provider metrics route remains a placeholder.
- Curie's smoke and coordinator repeat passed against live PostgreSQL, including CRUD, persisted updates, 422/404 and own-record cleanup. Script passed Black79/isort/flake8.
- Ohm's review found one proxy/config inheritance concern; all curl examples now use `-q --noproxy '*'`. Otherwise approved by static review. Restart commands documented but not exercised.
- A usage-limit error blocked the final documentation/commit on the previous turn. Existing files and running services were preserved. User then authorized continuation; limits now report 0% used. No reset was redeemed by the coordinator.
- Demo documentation checkpoint completed before adding reusable fixtures. No production code changed, no push/merge. Intentional API/PostgreSQL services remain available; agents are closed after their reports.

## 2026-09-26 - Reusable synthetic demo fixtures (completed locally)

- User requested persistent/reproducible test data for API and future frontend testing. Worktree `/private/tmp/investment-demo-fixtures`, branch `feature/reusable-demo-fixtures`, base `83940ea`.
- Decision: versioned JSON plus create-only HTTP seeder; keep the running API unchanged and avoid direct DB/private settings access. Default preview is GET-only; --apply explicit. Existing records/values remain unchanged; partial failures can be resumed by rerun, not rolled back across requests.
- Coordinator fixture: six explicitly synthetic companies, five currencies, 20 financial rows across2023-2025 annual/Q12026. Profit/loss/zero/null/no-reports scenarios. No real security data or unsupported ETF/bond claims.
- Existing live records include original `DEMO` and a user-created `string` ticker. Neither may be modified or removed by seeding.
- Developer Laplace owns `scripts/seed_demo.py` and `tests/test_seed_demo.py`; coordinator owns fixture/schema tests/documentation. Independent review follows before live writes.
- Fixture schema/scenario verification: two tests passed, six existing warnings. Full seed behavior tests/review/live application pending.
- Usage restarted at0% five-hour/weekly as reported by tool, not reset by coordinator; after preparation24% five-hour/4% weekly used. No exact context counter available.

### Verification and review
- Laplace implemented only seeder and unit tests. Initial TDD run failed collection because the implementation module did not exist; subsequent60 focused cases passed. This is new functionality, not a claim of reproducing an old application bug.
- Volta independently reviewed fixture, script, tests and guide: approved without actionable findings; 62 focused cases passed. Tests cover dry run, creation, repeatability, edits/unrelated records, timezone equivalence, pagination, collisions before writes, invalid fixtures and partial-failure resumption.
- Coordinator reran full isolated suite: **611 passed, six existing warnings**. Exact command from `/private/tmp`: `/usr/bin/env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/investment-demo-fixtures /Users/przemkowy/IdeaProjects/Investment-AI-Companion/.venv/bin/python -m pytest -q -p no:cacheprovider /private/tmp/investment-demo-fixtures/tests`.
- Default Black/isort/flake8 checks passed for `scripts/seed_demo.py`, `tests/test_seed_demo.py`, and `tests/test_demo_fixture.py` from the worktree. No production app/style/dependency changes.
- Live CLI dry run against verified loopback demo planned6companies/20metrics and performed no writes. First `--apply` created6companies/20metrics; second `--apply` created0/0 and skipped all6/20. UTC matching worked against PostgreSQL's offset timestamps.
- Compared pre-seed JSON snapshots against fresh API reads: both preexisting companies (including user-created ticker `string`) and original metrics row were unchanged. At verification total8companies/21metrics; fixture IDs6-11. IDs are not portable and docs do not rely on them.
- One initial coordinator curl snapshot command was rejected by shell globbing before any request; quoting the URL corrected the launcher. No data writes were involved in that error.

### Delivery and continuity
- Both agents closed. API and PostgreSQL intentionally remain running for the user. No other long-running process.
- Dataset/scenarios and commands: [demo-data](demo-data.md). API request/lifecycle examples: [api-demo](api-demo.md). JSON fixture is versioned and can repopulate a new isolated demo; temporary DB files are not backups.
- At final verification70% five-hour/11% weekly allowance was used. Completed this scope without another limit failure; no reset/purchase. Exact effort/model identity not independently measured; agents used inherited model.
- Work saved locally on `feature/reusable-demo-fixtures`; no push/merge. Remaining technical tasks are unchanged. Next separately authorized task can cover metric partial updates/null; do not reset the user's running demo to develop it.
