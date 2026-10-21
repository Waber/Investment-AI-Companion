"""Start the offline demo with one command.

    python -m scripts.run_demo

What that does, in order:

1. Picks a SQLite file under the repository's ``demo/`` directory
   (``demo/investment_demo.db``). That directory is git-ignored.
2. Refuses any other database URL. A personal PostgreSQL URL, a
   ``:memory:`` URL, a file outside ``demo/``, and a symlink in that
   path never get opened. ``Path.resolve`` follows links, so a
   ``demo`` directory that is a symlink would otherwise reset a
   database outside the checkout.
3. Checks that ``127.0.0.1`` and the chosen port are free. A second
   launch must not delete the live demo file and then fail to bind.
4. Deletes that file unless ``--keep`` was passed, then seeds the
   ``demo-v2`` fixture (stocks, ETFs, ETCs, and price bars). Seeding
   again skips rows that are already there.
5. Builds settings in code for that SQLite file, ``DATA_COLLECTOR=fake``,
   and loopback hosts. A ``DATABASE_URL`` in ``.env`` or in the shell is
   not used. A new ``SECRET_KEY`` is generated for this process even
   when the shell already has one. It is not printed and it is not
   written to a file.
6. Serves ``main:app`` with ``host="127.0.0.1"``. The URL printed is
   ``/ui`` when that page exists, otherwise ``/docs``.

``Settings`` reads ``.env`` from the working directory the first time
``app.core.config`` is imported. Environment variables win over that
file, and values passed to ``Settings(...)`` win over both. This module
therefore publishes the demo environment before it imports the app, and
then builds a ``Settings`` object with those values filled in. The
engine is created at import, so if it was already pointed somewhere
else it is replaced before anything connects.

Run it from the repository root so Python can import ``app`` and
``scripts``. The database path does not depend on the working directory.
"""

import argparse
import os
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path

DEMO_DIRECTORY_NAME = "demo"
DEMO_DATABASE_NAME = "investment_demo.db"
DEMO_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

# One message for every rejected URL. The URL itself is not included:
# a pasted PostgreSQL URL can contain a password.
_REFUSAL = (
    "The demo only opens the SQLite file it creates under demo/. "
    "Other database URLs are refused."
)


class DemoDatabaseRefused(ValueError):
    """The target is not the SQLite file this command creates."""


class DemoPortBusy(RuntimeError):
    """The loopback port is taken, so the database was left untouched."""


# Shown when a symlink would let reset leave the checkout. The target
# path is not included.
_SYMLINK_REFUSAL = (
    "The demo directory must be a real directory inside the checkout. "
    "A symlink in that path is refused."
)


@dataclass(frozen=True)
class DemoPlan:
    """The database, secret, and URL the demo process will use.

    ``secret_key`` is already chosen. Callers print ``database_path``
    and the HTTP URL, never ``secret_key``.
    """

    root: Path
    demo_dir: Path
    database_path: Path
    database_url: str
    secret_key: str
    host: str
    port: int
    open_path: str


def repo_root() -> Path:
    """Directory that contains ``app/`` and ``scripts/``."""
    return Path(__file__).resolve().parents[1]


def _absolute(path: Path) -> Path:
    """Absolute path that does not follow a symlink.

    ``Path.resolve`` would turn ``demo`` into the directory it points
    at. Later comparisons would then treat that outside directory as
    the demo.
    """
    return Path(os.path.abspath(path))


def refuse_symlink_escape(root: Path) -> Path:
    """Return ``root/demo`` only when reset cannot leave the checkout.

    A symlink at ``demo``, at the database file, or at a parent that
    is still inside the checkout is refused. That includes a ``root``
    argument that is itself a symlink: it is the parent of ``demo``.
    Following the link must also leave ``demo`` as a direct child of
    ``root``. The command's own checkout comes from ``__file__`` after
    ``resolve``, so a linked clone still works when the script is
    started as a module.
    """
    if Path(root).is_symlink():
        raise DemoDatabaseRefused(_SYMLINK_REFUSAL)
    root_abs = _absolute(root)
    demo = root_abs / DEMO_DIRECTORY_NAME
    current = demo / DEMO_DATABASE_NAME
    while current != root_abs:
        if current.is_symlink():
            raise DemoDatabaseRefused(_SYMLINK_REFUSAL)
        parent = current.parent
        if parent == current:
            break
        current = parent
    if demo.resolve().parent != root_abs.resolve():
        raise DemoDatabaseRefused(_SYMLINK_REFUSAL)
    return demo


def demo_directory(root: Path) -> Path:
    return refuse_symlink_escape(root)


def demo_database_path(root: Path) -> Path:
    return demo_directory(root) / DEMO_DATABASE_NAME


def sqlite_url_for(path: Path) -> str:
    """Absolute ``sqlite:///`` URL for ``path``.

    A relative URL would follow the process working directory. An
    absolute path already starts with ``/``, so the URL has four
    slashes: ``sqlite:////tmp/...``. The path is not ``resolve``d,
    so a symlink stays visible to the guard.
    """
    return "sqlite:///" + _absolute(path).as_posix()


def assert_owned_demo_database(url: str, demo_dir: Path) -> Path:
    """Return the demo file path, or raise without echoing ``url``.

    The only accepted target is the absolute SQLite file
    ``demo/investment_demo.db`` inside ``demo_dir``. A query string is
    refused because SQLite's URI mode can ignore the file. Symlinks are
    refused here as well: ``resolve`` would hide a ``demo`` directory
    that points outside the checkout, and reset would delete that file.
    """
    from sqlalchemy.engine.url import make_url
    from sqlalchemy.exc import ArgumentError

    try:
        parsed = make_url(url)
    except ArgumentError:
        raise DemoDatabaseRefused("Invalid database URL.") from None
    if (
        parsed.get_backend_name() != "sqlite"
        or parsed.query
        or parsed.username
        or parsed.password
        or parsed.host
    ):
        raise DemoDatabaseRefused(_REFUSAL)
    database = parsed.database
    if not database or database == ":memory:" or database.startswith("file:"):
        raise DemoDatabaseRefused(_REFUSAL)
    path = Path(database)
    if not path.is_absolute():
        raise DemoDatabaseRefused(_REFUSAL)
    demo_root = _absolute(demo_dir)
    file_path = _absolute(path)
    expected = _absolute(demo_root / DEMO_DATABASE_NAME)
    if file_path != expected or file_path.parent != demo_root:
        raise DemoDatabaseRefused(_REFUSAL)
    # ``demo_root`` is ``<checkout>/demo``. Its parent is the checkout.
    refuse_symlink_escape(demo_root.parent)
    return expected


def resolve_secret_key() -> str:
    """Generate a key for this demo process.

    A ``SECRET_KEY`` already in the shell or in ``.env`` is not reused.
    The demo publishes this new value so a later ``Settings()`` call
    does not fall through to the shell or the file. The value is not
    printed and it is not written to disk.
    """
    return secrets.token_urlsafe(32)


def demo_open_path(root: Path | None = None) -> str:
    """``/ui`` when the UI router is in this checkout, else ``/docs``."""
    base = repo_root() if root is None else root
    if (base / "app" / "ui" / "router.py").is_file():
        return "/ui"
    return "/docs"


def build_demo_plan(root: Path, *, port: int = DEFAULT_PORT) -> DemoPlan:
    """Choose the demo file and secret. Does not import the app."""
    path = demo_database_path(root)
    url = sqlite_url_for(path)
    assert_owned_demo_database(url, path.parent)
    return DemoPlan(
        root=root,
        demo_dir=path.parent,
        database_path=path,
        database_url=url,
        secret_key=resolve_secret_key(),
        host=DEMO_HOST,
        port=port,
        open_path=demo_open_path(root),
    )


def build_demo_settings(plan: DemoPlan):
    """Settings for this plan, ignoring ``.env`` and the shell database.

    Arguments passed here beat environment variables, which beat
    ``.env``. ``_env_file=None`` also skips the file for every other
    field, so a personal ``ALLOWED_HOSTS`` cannot widen the demo.
    """
    from app.core.config import Settings

    return Settings(
        _env_file=None,
        DATABASE_URL=plan.database_url,
        DATA_COLLECTOR="fake",
        SECRET_KEY=plan.secret_key,
        ALLOWED_HOSTS="localhost,127.0.0.1",
        DEBUG=False,
        BACKEND_CORS_ORIGINS="",
    )


def _copy_demo_settings(built) -> None:
    """Write the demo values onto the shared settings object.

    ``main`` and the collector dependency did ``from app.core.config
    import settings``. They hold that object, not a copy. Replacing
    the name on the config module would leave them with the old one,
    so the fields are updated in place.
    """
    import app.core.config as config_module

    current = config_module.settings
    current.DATABASE_URL = built.DATABASE_URL
    current.DATA_COLLECTOR = built.DATA_COLLECTOR
    current.SECRET_KEY = built.SECRET_KEY
    current.ALLOWED_HOSTS = built.ALLOWED_HOSTS
    current.DEBUG = built.DEBUG
    current.BACKEND_CORS_ORIGINS = built.BACKEND_CORS_ORIGINS


def _ensure_demo_engine(database_url: str) -> None:
    """Point the process engine at the demo file.

    ``database.py`` creates the engine while it is imported. If that
    happened before the demo URL was published, the engine still names
    the personal database. Replace it before ``init_db`` or a request
    can connect. ``init_db`` imported ``engine`` by name, so that
    binding is updated too.
    """
    from sqlalchemy.engine.url import make_url
    from sqlalchemy.orm import sessionmaker

    import app.core.database as database
    import app.core.init_db as init_db

    expected = make_url(database_url)
    current = database.engine.url
    same = (
        current.get_backend_name() == "sqlite"
        and bool(expected.database)
        and bool(current.database)
        and Path(current.database).resolve()
        == Path(expected.database).resolve()
    )
    if not same:
        database.engine = database.create_db_engine(database_url)
        database.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=database.engine,
        )
    init_db.engine = database.engine


def configure_demo_process(plan: DemoPlan):
    """Publish the demo environment, then import settings.

    The environment is set first so the object created at
    ``import app.core.config`` already has the SQLite URL. The explicit
    ``Settings`` object is still built and copied across, which covers
    a process that imported settings earlier (a test, or a future
    import at the top of this file).
    """
    os.environ["DATABASE_URL"] = plan.database_url
    os.environ["DATA_COLLECTOR"] = "fake"
    os.environ["SECRET_KEY"] = plan.secret_key
    os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1"
    os.environ["DEBUG"] = "false"
    os.environ["BACKEND_CORS_ORIGINS"] = ""
    built = build_demo_settings(plan)
    _copy_demo_settings(built)
    _ensure_demo_engine(built.DATABASE_URL)
    return built


def _sidecar_paths(path: Path) -> list[Path]:
    text = str(path)
    return [
        path,
        Path(text + "-wal"),
        Path(text + "-shm"),
        Path(text + "-journal"),
    ]


def ensure_port_is_free(port: int) -> None:
    """Raise when ``127.0.0.1:port`` is already taken.

    Call this before deleting the demo file. A second launch used to
    reset the database and then fail inside uvicorn, which destroyed
    the file the first process was serving.
    """
    import socket

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((DEMO_HOST, port))
    except OSError:
        raise DemoPortBusy(
            f"127.0.0.1:{port} is already in use. "
            "The demo database was not changed. "
            "Stop the other process or choose another --port."
        ) from None
    finally:
        probe.close()


def remove_database_files(path: Path) -> None:
    """Delete the demo database and SQLite's sidecar files.

    A directory is left alone and reported. A symlink at the file or
    at ``demo/`` is refused before unlink, so this cannot delete a
    database outside the checkout.
    """
    if path.is_symlink() or path.parent.is_symlink():
        raise DemoDatabaseRefused(_SYMLINK_REFUSAL)
    if path.is_dir():
        raise DemoDatabaseRefused("The demo database path is a directory.")
    for candidate in _sidecar_paths(path):
        if candidate.is_symlink() or candidate.is_file():
            candidate.unlink()


def seed_demo_database(plan: DemoPlan, *, reset: bool) -> dict:
    """Create tables and seed ``demo-v2`` into this plan's file.

    The guard runs again here so a caller cannot skip it. ``reset``
    deletes the file first, which is how a second run stays free of
    duplicate rows. ``--keep`` passes ``reset=False``; the seeder then
    skips fixture rows that are already stored.
    """
    refuse_symlink_escape(plan.root)
    assert_owned_demo_database(plan.database_url, plan.demo_dir)
    if reset:
        remove_database_files(plan.database_path)
    plan.demo_dir.mkdir(parents=True, exist_ok=True)
    from scripts.seed_demo import load_demo_v2, seed_sqlite_database

    return seed_sqlite_database(
        plan.database_url, apply=True, fixture=load_demo_v2()
    )


def demo_asgi_app(plan: DemoPlan):
    """An in-process app whose requests use the seeded demo file.

    Tests use this with ``httpx.ASGITransport``. It does not open a
    socket and it does not call ``init_db`` on the process engine, so
    the personal ``DATABASE_URL`` is not contacted.
    """
    from sqlalchemy.orm import sessionmaker

    from app.core.database import create_db_engine, get_db
    from main import create_app

    assert_owned_demo_database(plan.database_url, plan.demo_dir)
    engine = create_db_engine(plan.database_url)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    application = create_app(init_database_on_startup=False)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = override_get_db
    application.state.demo_engine = engine
    return application


def format_status(plan: DemoPlan, summary: dict) -> str:
    """Text for the console. The secret is not included."""
    companies = summary["companies"]
    metrics = summary["metrics"]
    prices = summary.get("prices") or {
        "created": 0,
        "skipped": 0,
    }
    lines = [
        "Offline demo",
        f"Database: {plan.database_path}",
        "Collector: fake",
        (
            f"Seeded {companies['created']} companies, "
            f"{metrics['created']} metrics, and "
            f"{prices['created']} prices."
        ),
    ]
    if companies["skipped"] or metrics["skipped"] or prices["skipped"]:
        lines.append(
            "Already present: "
            f"{companies['skipped']} companies, "
            f"{metrics['skipped']} metrics, and "
            f"{prices['skipped']} prices."
        )
    lines.append(f"Open http://{plan.host}:{plan.port}{plan.open_path}")
    return "\n".join(lines) + "\n"


def serve_demo(port: int) -> None:
    """Run uvicorn on loopback only.

    ``host="127.0.0.1"`` is passed here. The demo does not call
    ``python main.py`` and does not depend on the host in that file.
    """
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=port,
        reload=False,
    )


def _port(value: str) -> int:
    if not value.isdigit():
        raise argparse.ArgumentTypeError(
            "port must be an integer from 1 to 65535"
        )
    port = int(value)
    if port < 1 or port > 65535:
        raise argparse.ArgumentTypeError(
            "port must be an integer from 1 to 65535"
        )
    return port


def _parse_args(argv: list[str] | None):
    parser = argparse.ArgumentParser(
        description=(
            "Start the offline demo: a fresh SQLite file under demo/, "
            "the demo-v2 fixture, the fake collector, and a loopback server."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Delete the demo SQLite file before seeding. "
            "This is the default when --keep is not passed."
        ),
    )
    mode.add_argument(
        "--keep",
        action="store_true",
        help=(
            "Reuse the demo SQLite file and only insert missing fixture rows."
        ),
    )
    parser.add_argument(
        "--port",
        type=_port,
        default=DEFAULT_PORT,
        help="Loopback port (default 8000). The host is always 127.0.0.1.",
    )
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None, *, root: Path | None = None, serve=None
) -> int:
    """Seed the demo database and start the server. Return a status code."""
    from pydantic import ValidationError

    from scripts.seed_demo import SeedError

    args = _parse_args(argv)
    if serve is None:
        serve = serve_demo
    base = repo_root() if root is None else root
    try:
        # Before any reset. A busy port must leave the live file alone.
        ensure_port_is_free(args.port)
        plan = build_demo_plan(base, port=args.port)
        configure_demo_process(plan)
        summary = seed_demo_database(plan, reset=not args.keep)
    except (DemoDatabaseRefused, DemoPortBusy) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    except ValidationError:
        # The key may be inside the validation error. Print a fixed line.
        print(
            "FAIL: SECRET_KEY must be a random value of at least "
            "32 characters. The demo does not print the value.",
            file=sys.stderr,
        )
        return 1
    except (SeedError, OSError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(format_status(plan, summary), end="")
    serve(plan.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
