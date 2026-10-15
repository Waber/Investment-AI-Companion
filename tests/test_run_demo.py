"""The one-command offline demo stays on its own SQLite file.

These tests do not start uvicorn and do not open a socket. The
autouse network guard from ``tests/conftest.py`` stays on, including
for the in-process smoke test.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, settings
from app.core.database import create_db_engine
from app.models.company import CompanyCreate
from app.models.database_models import CompanyDB, FinancialMetricsDB
from app.repositories.company_repository import CompanyRepository
from scripts import run_demo
from scripts.run_demo import DemoDatabaseRefused

PROVIDED_SECRET = "unit-test-secret-key-0123456789abcd"
DOTENV_SECRET = "dotenv-secret-key-should-not-win-0123456789"
DOTENV_URL = (
    "postgresql://user:from-dotenv-secret@localhost:5432/investment_ai"
)
SHELL_URL = "postgresql://user:from-shell-secret@localhost:5432/investment_ai"


@pytest.fixture
def restore_process_settings():
    """Put the shared settings object and engine back after a demo run.

    ``configure_demo_process`` updates the process on purpose. A unit
    test that calls it must not leave the rest of the suite pointing
    at a temporary SQLite file.
    """
    import app.core.init_db as init_db
    from app.core import database

    keys = (
        "DATABASE_URL",
        "DATA_COLLECTOR",
        "SECRET_KEY",
        "ALLOWED_HOSTS",
        "DEBUG",
        "BACKEND_CORS_ORIGINS",
    )
    saved_env = {key: os.environ.get(key) for key in keys}
    saved = {
        "DATABASE_URL": settings.DATABASE_URL,
        "DATA_COLLECTOR": settings.DATA_COLLECTOR,
        "SECRET_KEY": settings.SECRET_KEY,
        "ALLOWED_HOSTS": settings.ALLOWED_HOSTS,
        "DEBUG": settings.DEBUG,
        "BACKEND_CORS_ORIGINS": settings.BACKEND_CORS_ORIGINS,
        "engine": database.engine,
        "SessionLocal": database.SessionLocal,
        "init_engine": init_db.engine,
    }
    yield
    for key, value in saved_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    settings.DATABASE_URL = saved["DATABASE_URL"]
    settings.DATA_COLLECTOR = saved["DATA_COLLECTOR"]
    settings.SECRET_KEY = saved["SECRET_KEY"]
    settings.ALLOWED_HOSTS = saved["ALLOWED_HOSTS"]
    settings.DEBUG = saved["DEBUG"]
    settings.BACKEND_CORS_ORIGINS = saved["BACKEND_CORS_ORIGINS"]
    if database.engine is not saved["engine"]:
        database.engine.dispose()
        database.engine = saved["engine"]
    database.SessionLocal = saved["SessionLocal"]
    init_db.engine = saved["init_engine"]


def _write_personal_dotenv(directory: Path) -> None:
    """A .env that must not become the demo database."""
    (directory / ".env").write_text(
        "\n".join(
            [
                f"DATABASE_URL={DOTENV_URL}",
                "DATA_COLLECTOR=yahoo",
                f"SECRET_KEY={DOTENV_SECRET}",
                "ALLOWED_HOSTS=evil.example",
                "DEBUG=true",
                "BACKEND_CORS_ORIGINS=http://evil.example",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _tickers(url: str) -> list[str]:
    engine = create_db_engine(url)
    try:
        session = sessionmaker(bind=engine)()
        try:
            return sorted(row.ticker for row in session.query(CompanyDB))
        finally:
            session.close()
    finally:
        engine.dispose()


def _counts(url: str) -> tuple[int, int]:
    engine = create_db_engine(url)
    try:
        session = sessionmaker(bind=engine)()
        try:
            return (
                session.query(CompanyDB).count(),
                session.query(FinancialMetricsDB).count(),
            )
        finally:
            session.close()
    finally:
        engine.dispose()


def test_demo_database_path_is_under_demo(tmp_path):
    path = run_demo.demo_database_path(tmp_path)
    assert path == (tmp_path / "demo" / "investment_demo.db").resolve()
    url = run_demo.sqlite_url_for(path)
    assert url.startswith("sqlite:///")
    assert run_demo.assert_owned_demo_database(url, path.parent) == path


def test_open_path_uses_ui_when_the_router_exists():
    assert run_demo.demo_open_path(run_demo.repo_root()) == "/ui"
    assert (run_demo.repo_root() / "app" / "ui" / "router.py").is_file()


def test_open_path_is_docs_without_the_ui(tmp_path):
    assert run_demo.demo_open_path(tmp_path) == "/docs"


def test_build_demo_settings_ignores_dotenv_and_the_shell(
    tmp_path, monkeypatch
):
    """Explicit settings win over .env and over DATABASE_URL in the shell."""
    monkeypatch.chdir(tmp_path)
    _write_personal_dotenv(tmp_path)
    monkeypatch.setenv("DATABASE_URL", SHELL_URL)
    monkeypatch.setenv("DATA_COLLECTOR", "yahoo")
    monkeypatch.setenv("ALLOWED_HOSTS", "evil.example")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.delenv("SECRET_KEY", raising=False)

    plan = run_demo.build_demo_plan(tmp_path, port=8123)
    built = run_demo.build_demo_settings(plan)

    assert built.DATABASE_URL == plan.database_url
    assert built.DATABASE_URL.startswith("sqlite:///")
    assert "postgresql" not in built.DATABASE_URL
    assert "from-dotenv-secret" not in built.DATABASE_URL
    assert "from-shell-secret" not in built.DATABASE_URL
    assert built.DATA_COLLECTOR == "fake"
    assert built.allowed_hosts == ["localhost", "127.0.0.1"]
    assert "0.0.0.0" not in built.allowed_hosts
    assert built.DEBUG is False
    assert built.BACKEND_CORS_ORIGINS == ""
    assert len(built.SECRET_KEY) >= 32
    assert built.SECRET_KEY != DOTENV_SECRET
    assert DOTENV_SECRET not in built.SECRET_KEY
    # The builder must not publish the key or create the database.
    assert not (tmp_path / "demo").exists()
    assert plan.secret_key not in (tmp_path / ".env").read_text(
        encoding="utf-8"
    )


def test_resolve_secret_key_prefers_an_explicit_value(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", PROVIDED_SECRET)
    explicit = "explicit-secret-key-0123456789abcd"
    assert run_demo.resolve_secret_key(explicit) == explicit


def test_blank_secret_is_replaced(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    generated = run_demo.resolve_secret_key("   ")
    assert generated != "   "
    assert len(generated) >= 32


def test_provided_secret_is_used_and_dotenv_secret_is_not(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _write_personal_dotenv(tmp_path)
    monkeypatch.setenv("SECRET_KEY", PROVIDED_SECRET)
    plan = run_demo.build_demo_plan(tmp_path)
    built = run_demo.build_demo_settings(plan)
    assert built.SECRET_KEY == PROVIDED_SECRET
    assert built.SECRET_KEY != DOTENV_SECRET


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://investment_ai@localhost:5432/investment_ai",
        "postgresql://user:super-secret-pass@db.internal:5432/investment_ai",
        "mysql://user:secret@localhost/investment_ai",
        "sqlite://",
        "sqlite:///:memory:",
        "sqlite:///investment_demo.db",
        "sqlite:///demo/other.db",
        "sqlite:///demo/nested/investment_demo.db",
    ],
)
def test_guard_rejects_non_demo_urls(tmp_path, url):
    demo = tmp_path / "demo"
    demo.mkdir()
    with pytest.raises(DemoDatabaseRefused) as caught:
        run_demo.assert_owned_demo_database(url, demo)
    text = str(caught.value)
    assert url not in text
    assert "super-secret-pass" not in text
    assert "secret@" not in text


def test_guard_rejects_paths_outside_the_demo_directory(tmp_path):
    demo = tmp_path / "demo"
    demo.mkdir()
    outside = tmp_path / "investment_demo.db"
    url = "sqlite:///" + outside.resolve().as_posix()
    with pytest.raises(DemoDatabaseRefused) as caught:
        run_demo.assert_owned_demo_database(url, demo)
    assert str(outside) not in str(caught.value)

    escaped = (demo / ".." / "investment_demo.db").resolve()
    escaped_url = "sqlite:///" + escaped.as_posix()
    with pytest.raises(DemoDatabaseRefused):
        run_demo.assert_owned_demo_database(escaped_url, demo)


def test_guard_rejects_a_query_and_an_unparseable_url(tmp_path):
    demo = tmp_path / "demo"
    path = demo / "investment_demo.db"
    query_url = run_demo.sqlite_url_for(path) + "?mode=memory"
    with pytest.raises(DemoDatabaseRefused):
        run_demo.assert_owned_demo_database(query_url, demo)

    with pytest.raises(
        DemoDatabaseRefused, match="^Invalid database URL\\.$"
    ) as caught:
        run_demo.assert_owned_demo_database("not a url", demo)
    assert "not a url" not in str(caught.value)


def test_guard_rejects_a_symlink_that_leaves_demo(tmp_path):
    demo = tmp_path / "demo"
    demo.mkdir()
    outside = tmp_path / "personal.db"
    outside.write_text("personal", encoding="utf-8")
    link = demo / "investment_demo.db"
    link.symlink_to(outside)
    url = run_demo.sqlite_url_for(link)
    with pytest.raises(DemoDatabaseRefused):
        run_demo.assert_owned_demo_database(url, demo)
    assert outside.read_text(encoding="utf-8") == "personal"


def test_uvicorn_config_uses_loopback(monkeypatch):
    import uvicorn

    seen = {}

    def fake_run(app, **kwargs):
        seen["app"] = app
        seen.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    run_demo.serve_demo(8123)
    assert seen["app"] == "main:app"
    assert seen["host"] == "127.0.0.1"
    assert seen["port"] == 8123
    assert seen["reload"] is False
    assert "0.0.0.0" not in seen.values()


def test_configure_replaces_a_personal_database_url(
    tmp_path, monkeypatch, restore_process_settings
):
    monkeypatch.chdir(tmp_path)
    _write_personal_dotenv(tmp_path)
    monkeypatch.setenv("DATABASE_URL", SHELL_URL)
    monkeypatch.setenv("DATA_COLLECTOR", "yahoo")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    before = settings.DATABASE_URL

    plan = run_demo.build_demo_plan(tmp_path)
    built = run_demo.configure_demo_process(plan)

    from app.core.database import engine

    assert before.startswith("postgresql://")
    assert settings.DATABASE_URL == plan.database_url
    assert built.DATABASE_URL == plan.database_url
    assert settings.DATA_COLLECTOR == "fake"
    assert settings.allowed_hosts == ["localhost", "127.0.0.1"]
    assert settings.DEBUG is False
    assert settings.SECRET_KEY == plan.secret_key
    assert settings.SECRET_KEY != DOTENV_SECRET
    assert engine.url.get_backend_name() == "sqlite"
    assert Path(engine.url.database).resolve() == plan.database_path
    # Configuring the process does not create or open the file.
    assert not plan.database_path.exists()


def test_child_process_does_not_inherit_dotenv_database(tmp_path):
    """A fresh interpreter is what ``python -m scripts.run_demo`` starts.

    The in-process suite has already imported settings. This child
    imports them only after the demo has published its own environment,
    with a personal ``.env`` sitting in the working directory.
    """
    _write_personal_dotenv(tmp_path)
    child_lines = [
        "import sys",
        "from pathlib import Path",
        "from scripts.run_demo import build_demo_plan",
        "from scripts.run_demo import configure_demo_process",
        "plan = build_demo_plan(Path(sys.argv[1]))",
        "configure_demo_process(plan)",
        "import main",
        "from app.core.config import settings",
        "from app.core.database import engine",
        "from starlette.middleware.trustedhost import TrustedHostMiddleware",
        "hosts = []",
        "for layer in main.app.user_middleware:",
        "    if layer.cls is TrustedHostMiddleware:",
        "        hosts = list(layer.kwargs.get('allowed_hosts', []))",
        "print('database_url=' + settings.DATABASE_URL)",
        "print('backend=' + engine.url.get_backend_name())",
        "print('database=' + str(engine.url.database))",
        "print('collector=' + settings.DATA_COLLECTOR)",
        "print('hosts=' + ','.join(settings.allowed_hosts))",
        "print('debug=' + str(settings.DEBUG).lower())",
        "same = settings.SECRET_KEY == {secret!r}",
        "print('secret_is_dotenv=' + str(same).lower())",
        "url = settings.DATABASE_URL",
        "print('dotenv_password=' + str('from-dotenv-secret' in url).lower())",
        "print('shell_password=' + str('from-shell-secret' in url).lower())",
        "print('middleware=' + ','.join(hosts))",
        "match = plan.secret_key == settings.SECRET_KEY",
        "print('secret_matches_plan=' + str(match).lower())",
    ]
    script = "\n".join(child_lines).format(secret=DOTENV_SECRET)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(run_demo.repo_root()),
        "DATABASE_URL": SHELL_URL,
        "DATA_COLLECTOR": "yahoo",
        "ALLOWED_HOSTS": "evil.example",
        "DEBUG": "true",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    reported = {}
    for line in completed.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        reported[key] = value
    assert reported["database_url"].startswith("sqlite:///")
    assert reported["backend"] == "sqlite"
    assert (
        Path(reported["database"]).resolve()
        == (tmp_path / "demo" / "investment_demo.db").resolve()
    )
    assert reported["collector"] == "fake"
    assert reported["hosts"] == "localhost,127.0.0.1"
    assert reported["debug"] == "false"
    assert reported["secret_is_dotenv"] == "false"
    assert reported["dotenv_password"] == "false"
    assert reported["shell_password"] == "false"
    assert reported["middleware"] == "localhost,127.0.0.1"
    assert reported["secret_matches_plan"] == "true"
    assert DOTENV_SECRET not in completed.stdout
    assert "from-dotenv-secret" not in completed.stdout
    assert "from-shell-secret" not in completed.stdout
    assert not (run_demo.repo_root() / "demo").exists()


def test_fresh_seed_twice_has_no_duplicates(tmp_path):
    plan = run_demo.build_demo_plan(tmp_path)
    before = settings.DATABASE_URL
    first = run_demo.seed_demo_database(plan, reset=True)
    assert first["companies"]["created"] == 6
    assert first["metrics"]["created"] == 20
    assert _counts(plan.database_url) == (6, 20)

    engine = create_db_engine(plan.database_url)
    try:
        session = sessionmaker(bind=engine)()
        try:
            CompanyRepository(session).create(
                CompanyCreate(name="Extra Demo", ticker="DEMO_EXTRA")
            )
        finally:
            session.close()
    finally:
        engine.dispose()
    assert "DEMO_EXTRA" in _tickers(plan.database_url)

    kept = run_demo.seed_demo_database(plan, reset=False)
    assert kept["companies"]["created"] == 0
    assert kept["companies"]["skipped"] == 6
    assert kept["metrics"]["created"] == 0
    assert kept["metrics"]["skipped"] == 20
    assert _counts(plan.database_url) == (7, 20)

    second = run_demo.seed_demo_database(plan, reset=True)
    assert second["companies"]["created"] == 6
    assert second["metrics"]["created"] == 20
    assert _tickers(plan.database_url) == sorted(
        [
            "DEMO_DE_INDUSTRY",
            "DEMO_JP_STABLE",
            "DEMO_PL_EMPTY",
            "DEMO_PL_TECH",
            "DEMO_SG_EARLY",
            "DEMO_US_GROWTH",
        ]
    )
    assert settings.DATABASE_URL == before


def test_reset_removes_sqlite_sidecars(tmp_path):
    plan = run_demo.build_demo_plan(tmp_path)
    plan.demo_dir.mkdir()
    plan.database_path.write_text("old", encoding="utf-8")
    wal = Path(str(plan.database_path) + "-wal")
    wal.write_text("wal", encoding="utf-8")
    run_demo.seed_demo_database(plan, reset=True)
    assert not wal.exists()
    assert _counts(plan.database_url) == (6, 20)


def test_reset_refuses_to_replace_a_directory(tmp_path):
    plan = run_demo.build_demo_plan(tmp_path)
    plan.database_path.mkdir(parents=True)
    with pytest.raises(DemoDatabaseRefused, match="directory"):
        run_demo.seed_demo_database(plan, reset=True)


def test_main_prints_the_ui_url_and_not_the_secret(
    tmp_path, monkeypatch, capsys, restore_process_settings
):
    monkeypatch.setattr(run_demo, "demo_open_path", lambda root: "/ui")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    served = []

    code = run_demo.main(
        ["--port", "8765"],
        root=tmp_path,
        serve=lambda port: served.append(port),
    )
    captured = capsys.readouterr()
    assert code == 0
    assert served == [8765]
    assert "http://127.0.0.1:8765/ui" in captured.out
    assert "0.0.0.0" not in captured.out
    assert "Collector: fake" in captured.out
    assert "Seeded 6 companies and 20 metrics." in captured.out
    secret = settings.SECRET_KEY
    assert secret not in captured.out
    assert secret not in captured.err
    assert DOTENV_SECRET not in captured.out
    database = tmp_path / "demo" / "investment_demo.db"
    assert secret.encode() not in database.read_bytes()
    assert not (tmp_path / ".env").exists()


def test_main_keep_does_not_duplicate_rows(
    tmp_path, monkeypatch, capsys, restore_process_settings
):
    monkeypatch.setattr(run_demo, "demo_open_path", lambda root: "/docs")
    run_demo.main([], root=tmp_path, serve=lambda port: None)
    capsys.readouterr()
    code = run_demo.main(
        ["--keep", "--port", "8000"],
        root=tmp_path,
        serve=lambda port: None,
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "http://127.0.0.1:8000/docs" in captured.out
    assert "Seeded 0 companies and 0 metrics." in captured.out
    assert "Already present: 6 companies and 20 metrics." in captured.out
    plan = run_demo.build_demo_plan(tmp_path)
    assert _counts(plan.database_url) == (6, 20)


def test_main_refuses_a_non_demo_url_without_serving(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(
        run_demo,
        "sqlite_url_for",
        lambda path: "postgresql://user:secret-token@localhost/investment_ai",
    )
    served = []
    code = run_demo.main(
        [],
        root=tmp_path,
        serve=lambda port: served.append(port),
    )
    captured = capsys.readouterr()
    assert code == 1
    assert served == []
    assert "secret-token" not in captured.err
    assert "postgresql://" not in captured.err
    assert "FAIL:" in captured.err


def test_main_rejects_a_short_secret_without_printing_it(
    tmp_path, monkeypatch, capsys, restore_process_settings
):
    monkeypatch.setenv("SECRET_KEY", "too-short")
    served = []
    code = run_demo.main(
        [],
        root=tmp_path,
        serve=lambda port: served.append(port),
    )
    captured = capsys.readouterr()
    assert code == 1
    assert served == []
    assert "too-short" not in captured.out
    assert "too-short" not in captured.err


def test_main_serves_with_the_loopback_runner(
    tmp_path, monkeypatch, restore_process_settings
):
    served = []
    monkeypatch.setattr(
        run_demo, "serve_demo", lambda port: served.append(port)
    )
    code = run_demo.main(["--port", "8123"], root=tmp_path)
    assert code == 0
    assert served == [8123]


def test_main_reports_a_seed_failure(
    tmp_path, monkeypatch, capsys, restore_process_settings
):
    from scripts.seed_demo import SeedError

    def boom(plan, *, reset):
        raise SeedError("seed failed")

    monkeypatch.setattr(run_demo, "seed_demo_database", boom)
    served = []
    code = run_demo.main(
        [],
        root=tmp_path,
        serve=lambda port: served.append(port),
    )
    captured = capsys.readouterr()
    assert code == 1
    assert served == []
    assert "seed failed" in captured.err
    assert "FAIL:" in captured.err


def test_main_rejects_reset_and_keep_together():
    with pytest.raises(SystemExit) as caught:
        run_demo.main(["--reset", "--keep"])
    assert caught.value.code == 2


@pytest.mark.parametrize("port", ["0", "70000", "nope"])
def test_main_rejects_a_bad_port(port):
    with pytest.raises(SystemExit) as caught:
        run_demo.main(["--port", port])
    assert caught.value.code == 2


@pytest.mark.asyncio
async def test_smoke_seeds_and_serves_pages_without_a_server(tmp_path):
    """Seed demo-v1 and request the API, /docs, and /ui in-process.

    ``ASGITransport`` does not open a socket. The network guard is the
    autouse fixture, so a real provider call fails this test.
    """
    before = settings.DATABASE_URL
    plan = run_demo.build_demo_plan(tmp_path, port=8000)
    summary = run_demo.seed_demo_database(plan, reset=True)
    assert summary["companies"]["created"] == 6
    app = run_demo.demo_asgi_app(plan)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://127.0.0.1",
        ) as client:
            root = await client.get("/")
            docs = await client.get("/docs")
            companies = await client.get("/api/v1/companies/?skip=0&limit=100")
            fetched = await client.post(
                "/api/v1/data-collection/fetch-company",
                json={"ticker": "DEMO_PL_TECH"},
            )
            missing = await client.post(
                "/api/v1/data-collection/fetch-company",
                json={"ticker": "NOTREAL"},
            )
            assert root.status_code == 200
            assert root.json()["docs_url"] == "/docs"
            assert docs.status_code == 200
            assert companies.status_code == 200
            rows = companies.json()
            assert len(rows) == 6
            tickers = {row["ticker"] for row in rows}
            assert "DEMO_PL_TECH" in tickers
            tech = next(row for row in rows if row["ticker"] == "DEMO_PL_TECH")
            metrics = await client.get(
                f"/api/v1/financial-metrics/company/{tech['id']}"
                "?skip=0&limit=100"
            )
            assert metrics.status_code == 200
            assert len(metrics.json()) >= 1
            assert fetched.status_code == 200
            assert fetched.json()["success"] is True
            assert missing.status_code == 404
            again = await client.get("/api/v1/companies/?skip=0&limit=100")
            assert len(again.json()) == 6

            if run_demo.demo_open_path() == "/ui":
                page = await client.get("/ui")
                assert page.status_code == 200
                assert "DEMO_PL_TECH" in page.text
                assert 'href="/static/ui.css"' in page.text
                detail = await client.get("/ui/instruments/1")
                assert detail.status_code == 200
    finally:
        app.state.demo_engine.dispose()

    assert settings.DATABASE_URL == before
    assert settings.DATA_COLLECTOR == "fake"


def test_plain_settings_after_configure_still_ignore_dotenv(
    tmp_path, monkeypatch, restore_process_settings
):
    """The object ``main.py`` imported must match the explicit settings.

    A later ``Settings()`` also reads ``.env``. Environment variables
    published by the demo win over that file.
    """
    monkeypatch.chdir(tmp_path)
    _write_personal_dotenv(tmp_path)
    monkeypatch.setenv("DATABASE_URL", SHELL_URL)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    plan = run_demo.build_demo_plan(tmp_path)
    run_demo.configure_demo_process(plan)
    loaded = Settings()
    assert loaded.DATABASE_URL == plan.database_url
    assert loaded.DATA_COLLECTOR == "fake"
    assert loaded.SECRET_KEY == plan.secret_key
    assert loaded.allowed_hosts == ["localhost", "127.0.0.1"]
    assert "from-dotenv-secret" not in loaded.DATABASE_URL
