"""The one-command offline demo stays on its own SQLite file.

These tests do not start uvicorn and do not connect off this machine.
The autouse network guard from ``tests/conftest.py`` stays on,
including for the in-process smoke test. ``main`` binds ``127.0.0.1``
only long enough to see that the port is free, then closes that socket.
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
from app.models.database_models import (
    CompanyDB,
    FinancialMetricsDB,
    PriceBarDB,
)
from app.repositories.company_repository import CompanyRepository
from scripts import run_demo
from scripts.run_demo import DemoDatabaseRefused
from scripts.seed_demo import load_demo_v2

PROVIDED_SECRET = "unit-test-secret-key-0123456789abcd"
DOTENV_SECRET = "dotenv-secret-key-should-not-win-0123456789"
DOTENV_URL = (
    "postgresql://user:from-dotenv-secret@localhost:5432/investment_ai"
)
SHELL_URL = "postgresql://user:from-shell-secret@localhost:5432/investment_ai"

_V2 = load_demo_v2()
V2_COMPANIES = len(_V2["companies"])
V2_METRICS = sum(len(item["metrics"]) for item in _V2["companies"])
V2_PRICES = sum(len(item["prices"]) for item in _V2["companies"])
V2_TICKERS = sorted(item["company"]["ticker"] for item in _V2["companies"])


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


def _counts(url: str) -> tuple[int, int, int]:
    engine = create_db_engine(url)
    try:
        session = sessionmaker(bind=engine)()
        try:
            return (
                session.query(CompanyDB).count(),
                session.query(FinancialMetricsDB).count(),
                session.query(PriceBarDB).count(),
            )
        finally:
            session.close()
    finally:
        engine.dispose()


def test_demo_database_path_is_under_demo(tmp_path):
    path = run_demo.demo_database_path(tmp_path)
    assert path == tmp_path / "demo" / "investment_demo.db"
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
    monkeypatch.setenv("SECRET_KEY", PROVIDED_SECRET)

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
    assert built.SECRET_KEY != PROVIDED_SECRET
    assert DOTENV_SECRET not in built.SECRET_KEY
    # The builder must not publish the key or create the database.
    assert not (tmp_path / "demo").exists()
    assert plan.secret_key not in (tmp_path / ".env").read_text(
        encoding="utf-8"
    )


def test_resolve_secret_key_ignores_the_shell(monkeypatch):
    """A key already in the environment is not the demo key."""
    monkeypatch.setenv("SECRET_KEY", PROVIDED_SECRET)
    generated = run_demo.resolve_secret_key()
    assert generated != PROVIDED_SECRET
    assert len(generated) >= 32
    assert run_demo.resolve_secret_key() != generated


def test_blank_shell_secret_is_not_reused(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "   ")
    generated = run_demo.resolve_secret_key()
    assert generated.strip() != ""
    assert generated != "   "
    assert len(generated) >= 32


def test_shell_secret_and_dotenv_secret_are_not_reused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_personal_dotenv(tmp_path)
    monkeypatch.setenv("SECRET_KEY", PROVIDED_SECRET)
    plan = run_demo.build_demo_plan(tmp_path)
    built = run_demo.build_demo_settings(plan)
    assert built.SECRET_KEY == plan.secret_key
    assert built.SECRET_KEY != PROVIDED_SECRET
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


def test_symlink_demo_directory_is_refused_and_not_deleted(tmp_path, capsys):
    """``demo/`` as a symlink must not reset the directory it points at.

    ``Path.resolve`` follows the link. Comparing the resolved paths
    would then treat the outside file as the demo database and delete
    it. The command refuses before seeding.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    personal = outside / "investment_demo.db"
    personal.write_text("personal-data", encoding="utf-8")
    (tmp_path / "demo").symlink_to(outside, target_is_directory=True)
    served = []
    code = run_demo.main(
        ["--port", str(_free_loopback_port())],
        root=tmp_path,
        serve=lambda port: served.append(port),
    )
    captured = capsys.readouterr()
    assert code == 1
    assert served == []
    assert "symlink" in captured.err.casefold()
    assert personal.read_text(encoding="utf-8") == "personal-data"
    assert "outside" not in captured.err


def test_symlink_parent_inside_the_checkout_is_refused(tmp_path):
    """A parent of ``demo`` that is still inside the checkout is refused.

    Here the parent is the directory passed as the checkout. It lives
    inside ``checkout/`` and points at a database outside it.
    """
    outside = tmp_path / "outside"
    (outside / "demo").mkdir(parents=True)
    personal = outside / "demo" / "investment_demo.db"
    personal.write_text("personal", encoding="utf-8")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    linked = checkout / "nested"
    linked.symlink_to(outside, target_is_directory=True)
    with pytest.raises(DemoDatabaseRefused, match="symlink"):
        run_demo.build_demo_plan(linked)
    assert personal.read_text(encoding="utf-8") == "personal"


def test_remove_refuses_a_symlink_before_unlink(tmp_path):
    """The delete step itself refuses a link, not only the earlier guard."""
    outside = tmp_path / "outside"
    outside.mkdir()
    personal = outside / "investment_demo.db"
    personal.write_text("personal", encoding="utf-8")
    demo = tmp_path / "demo"
    demo.symlink_to(outside, target_is_directory=True)
    with pytest.raises(DemoDatabaseRefused, match="symlink"):
        run_demo.remove_database_files(demo / "investment_demo.db")
    assert personal.read_text(encoding="utf-8") == "personal"

    real_demo = tmp_path / "real-demo"
    real_demo.mkdir()
    linked_file = real_demo / "investment_demo.db"
    linked_file.symlink_to(personal)
    with pytest.raises(DemoDatabaseRefused, match="symlink"):
        run_demo.remove_database_files(linked_file)
    assert personal.read_text(encoding="utf-8") == "personal"
    assert linked_file.is_symlink()


def test_symlink_between_the_checkout_and_demo_is_refused(
    tmp_path, monkeypatch
):
    """An intermediate directory under the checkout is refused too."""
    outside = tmp_path / "outside"
    (outside / "inner").mkdir(parents=True)
    personal = outside / "inner" / "investment_demo.db"
    personal.write_text("personal", encoding="utf-8")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "demo").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(run_demo, "DEMO_DIRECTORY_NAME", "demo/inner")
    with pytest.raises(DemoDatabaseRefused, match="symlink"):
        run_demo.refuse_symlink_escape(checkout)
    assert personal.read_text(encoding="utf-8") == "personal"


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
    monkeypatch.setenv("SECRET_KEY", PROVIDED_SECRET)
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
    assert settings.SECRET_KEY != PROVIDED_SECRET
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
        "shell_same = settings.SECRET_KEY == {shell!r}",
        "print('secret_is_shell=' + str(shell_same).lower())",
        "url = settings.DATABASE_URL",
        "print('dotenv_password=' + str('from-dotenv-secret' in url).lower())",
        "print('shell_password=' + str('from-shell-secret' in url).lower())",
        "print('middleware=' + ','.join(hosts))",
        "match = plan.secret_key == settings.SECRET_KEY",
        "print('secret_matches_plan=' + str(match).lower())",
    ]
    script = "\n".join(child_lines).format(
        secret=DOTENV_SECRET, shell=PROVIDED_SECRET
    )
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(run_demo.repo_root()),
        "DATABASE_URL": SHELL_URL,
        "SECRET_KEY": PROVIDED_SECRET,
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
    assert reported["secret_is_shell"] == "false"
    assert reported["dotenv_password"] == "false"
    assert reported["shell_password"] == "false"
    assert reported["middleware"] == "localhost,127.0.0.1"
    assert reported["secret_matches_plan"] == "true"
    assert DOTENV_SECRET not in completed.stdout
    assert PROVIDED_SECRET not in completed.stdout
    assert "from-dotenv-secret" not in completed.stdout
    assert "from-shell-secret" not in completed.stdout
    assert not (run_demo.repo_root() / "demo").exists()


def test_fresh_seed_twice_has_no_duplicates(tmp_path):
    plan = run_demo.build_demo_plan(tmp_path)
    before = settings.DATABASE_URL
    first = run_demo.seed_demo_database(plan, reset=True)
    assert first["companies"]["created"] == V2_COMPANIES
    assert first["metrics"]["created"] == V2_METRICS
    assert first["prices"]["created"] == V2_PRICES
    assert _counts(plan.database_url) == (V2_COMPANIES, V2_METRICS, V2_PRICES)

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
    assert kept["companies"]["skipped"] == V2_COMPANIES
    assert kept["metrics"]["created"] == 0
    assert kept["metrics"]["skipped"] == V2_METRICS
    assert kept["prices"]["created"] == 0
    assert kept["prices"]["skipped"] == V2_PRICES
    assert _counts(plan.database_url) == (
        V2_COMPANIES + 1,
        V2_METRICS,
        V2_PRICES,
    )

    second = run_demo.seed_demo_database(plan, reset=True)
    assert second["companies"]["created"] == V2_COMPANIES
    assert second["metrics"]["created"] == V2_METRICS
    assert second["prices"]["created"] == V2_PRICES
    assert _tickers(plan.database_url) == V2_TICKERS
    assert settings.DATABASE_URL == before


def test_reset_removes_sqlite_sidecars(tmp_path):
    plan = run_demo.build_demo_plan(tmp_path)
    plan.demo_dir.mkdir()
    plan.database_path.write_text("old", encoding="utf-8")
    wal = Path(str(plan.database_path) + "-wal")
    wal.write_text("wal", encoding="utf-8")
    run_demo.seed_demo_database(plan, reset=True)
    assert not wal.exists()
    assert _counts(plan.database_url) == (V2_COMPANIES, V2_METRICS, V2_PRICES)


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
    assert (
        f"Seeded {V2_COMPANIES} companies, {V2_METRICS} metrics, "
        f"and {V2_PRICES} prices."
    ) in captured.out
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
    assert "Seeded 0 companies, 0 metrics, and 0 prices." in captured.out
    assert (
        f"Already present: {V2_COMPANIES} companies, "
        f"{V2_METRICS} metrics, and {V2_PRICES} prices."
    ) in captured.out
    plan = run_demo.build_demo_plan(tmp_path)
    assert _counts(plan.database_url) == (V2_COMPANIES, V2_METRICS, V2_PRICES)


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


def test_main_ignores_a_short_shell_secret(
    tmp_path, monkeypatch, capsys, restore_process_settings
):
    """A short SECRET_KEY in the shell is not used and is not printed."""
    monkeypatch.setenv("SECRET_KEY", "too-short")
    served = []
    code = run_demo.main(
        ["--port", str(_free_loopback_port())],
        root=tmp_path,
        serve=lambda port: served.append(port),
    )
    captured = capsys.readouterr()
    assert code == 0
    assert served
    assert settings.SECRET_KEY != "too-short"
    assert len(settings.SECRET_KEY) >= 32
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


def test_busy_port_does_not_reset_the_database(tmp_path, capsys):
    """A taken port fails before the live demo file is deleted."""
    import socket

    plan = run_demo.build_demo_plan(tmp_path)
    run_demo.seed_demo_database(plan, reset=True)
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

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.listen(1)
    served = []
    try:
        code = run_demo.main(
            ["--port", str(port)],
            root=tmp_path,
            serve=lambda chosen: served.append(chosen),
        )
    finally:
        probe.close()
    captured = capsys.readouterr()
    assert code == 1
    assert served == []
    assert "already in use" in captured.err
    assert "not changed" in captured.err
    assert "DEMO_EXTRA" in _tickers(plan.database_url)
    assert _counts(plan.database_url) == (
        V2_COMPANIES + 1,
        V2_METRICS,
        V2_PRICES,
    )


def _free_loopback_port() -> int:
    """A loopback port that is free at the moment this returns."""
    import socket

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]
    finally:
        probe.close()


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
    """Seed demo-v2 and request the API, /docs, and /ui in-process.

    ``ASGITransport`` does not open a socket. The network guard is the
    autouse fixture, so a real provider call fails this test.
    """
    before = settings.DATABASE_URL
    plan = run_demo.build_demo_plan(tmp_path, port=8000)
    summary = run_demo.seed_demo_database(plan, reset=True)
    assert summary["companies"]["created"] == V2_COMPANIES
    assert summary["prices"]["created"] == V2_PRICES
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
            assert len(rows) == V2_COMPANIES
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
            assert len(again.json()) == V2_COMPANIES
            prices = await client.get(
                f"/api/v1/instruments/{tech['id']}/prices"
            )
            assert prices.status_code == 200
            assert prices.json()
            assert prices.json()[0]["source"] == "[IAC-DEMO-V2]"
            empty = next(
                row for row in rows if row["ticker"] == "DEMO_PL_EMPTY"
            )
            no_prices = await client.get(
                f"/api/v1/instruments/{empty['id']}/prices"
            )
            assert no_prices.status_code == 200
            assert no_prices.json() == []

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
    monkeypatch.setenv("SECRET_KEY", PROVIDED_SECRET)
    plan = run_demo.build_demo_plan(tmp_path)
    run_demo.configure_demo_process(plan)
    loaded = Settings()
    assert loaded.DATABASE_URL == plan.database_url
    assert loaded.DATA_COLLECTOR == "fake"
    assert loaded.SECRET_KEY == plan.secret_key
    assert loaded.SECRET_KEY != PROVIDED_SECRET
    assert loaded.allowed_hosts == ["localhost", "127.0.0.1"]
    assert "from-dotenv-secret" not in loaded.DATABASE_URL
