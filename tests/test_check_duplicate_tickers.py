"""The preflight that revision 0003 runs before it adds an index."""

from sqlalchemy import create_engine, text

from scripts.check_duplicate_tickers import (
    CompaniesTableMissing,
    duplicate_tickers,
    main,
)


def test_script_reports_duplicate_tickers_and_leaves_the_rows(
    tmp_path, capsys
):
    path = tmp_path / "dups.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, "
                "ticker VARCHAR(20) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO companies (ticker) VALUES ('AAA'), ('AAA'), "
                "('BRK.B'), ('BRK.B'), ('BRK.B')"
            )
        )
    engine.dispose()

    url = f"sqlite:///{path}"
    assert main(["check", url]) == 1
    error = capsys.readouterr().err
    assert "'AAA' (2 rows)" in error
    assert "'BRK.B' (3 rows)" in error
    assert "did not change those rows" in error

    engine = create_engine(url)
    with engine.connect() as connection:
        assert duplicate_tickers(connection) == [
            ("AAA", [("AAA", 2)]),
            ("BRK.B", [("BRK.B", 3)]),
        ]
        assert (
            connection.execute(text("SELECT COUNT(*) FROM companies")).scalar()
            == 5
        )
    engine.dispose()


def test_script_is_quiet_when_every_ticker_is_unique(tmp_path, capsys):
    path = tmp_path / "clean.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, ticker VARCHAR(20) NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO companies (ticker) VALUES ('AAA')")
        )
    engine.dispose()

    assert main(["check", f"sqlite:///{path}"]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "No duplicate tickers."
    assert captured.err == ""


def test_script_rejects_a_missing_table_and_a_missing_url(
    tmp_path, capsys, monkeypatch
):
    path = tmp_path / "empty.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE other (id INTEGER)"))
    engine.dispose()

    assert main(["check", f"sqlite:///{path}"]) == 2
    assert "companies table is not in this database" in capsys.readouterr().err

    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert main(["check"]) == 2
    assert "Usage:" in capsys.readouterr().err
    assert main(["check", "   "]) == 2


def test_script_reports_case_and_space_collisions_without_rewriting(
    tmp_path, capsys
):
    """``aapl`` and ``AAPL `` match after trim and uppercase.

    The message names both stored values. The rows stay as inserted.
    """
    path = tmp_path / "case.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, ticker VARCHAR(20) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO companies (id, ticker) VALUES "
                "(1, 'aapl'), (2, 'AAPL ')"
            )
        )
    engine.dispose()

    url = f"sqlite:///{path}"
    assert main(["check", url]) == 1
    error = capsys.readouterr().err
    assert "'aapl'" in error
    assert "'AAPL '" in error
    assert "did not change those rows" in error
    assert "Traceback" not in error

    engine = create_engine(url)
    with engine.connect() as connection:
        assert duplicate_tickers(connection) == [
            ("AAPL", [("AAPL ", 1), ("aapl", 1)])
        ]
        stored = (
            connection.execute(
                text("SELECT ticker FROM companies ORDER BY id")
            )
            .scalars()
            .all()
        )
        assert stored == ["aapl", "AAPL "]
    engine.dispose()


_BAD_URL = "postgresql://u:secret@[bad"
_URL_LINE = "Could not read companies: the database URL is not valid.\n"
_READ_LINE = (
    "Could not read companies: the database is unreachable "
    "or the table is missing.\n"
)


def _assert_secret_stays_hidden(captured):
    assert "secret" not in captured.out
    assert "secret" not in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_malformed_url_argument_hides_the_password(capsys, monkeypatch):
    """The reviewer's URL exits 1 and never prints the password."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert main(["check", _BAD_URL]) == 1
    captured = capsys.readouterr()
    _assert_secret_stays_hidden(captured)
    assert captured.err in (_URL_LINE, _READ_LINE)
    assert captured.out == ""


def test_malformed_url_environment_hides_the_password(capsys, monkeypatch):
    """DATABASE_URL is used when the command has no URL argument."""
    monkeypatch.setenv("DATABASE_URL", _BAD_URL)
    assert main(["check"]) == 1
    captured = capsys.readouterr()
    _assert_secret_stays_hidden(captured)
    assert captured.err in (_URL_LINE, _READ_LINE)
    assert captured.out == ""


def test_unparsed_url_uses_the_fixed_url_line(capsys, monkeypatch):
    """A URL SQLAlchemy cannot parse includes the password in its text."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert main(["check", "u:secret@[bad"]) == 1
    captured = capsys.readouterr()
    assert captured.err == _URL_LINE
    _assert_secret_stays_hidden(captured)


def test_sqlalchemy_error_uses_the_fixed_read_line(monkeypatch, capsys):
    """Driver text is not the message the operator sees.

    The URL is PostgreSQL, not a missing SQLite file. A missing file
    is refused before ``create_engine``, so this stand-in would never
    run for ``sqlite:///unused.db``.
    """
    from sqlalchemy.exc import SQLAlchemyError

    def explode(_url):
        raise SQLAlchemyError("driver text includes secret")

    monkeypatch.setattr(
        "scripts.check_duplicate_tickers.create_engine", explode
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert main(["check", "postgresql://localhost/db"]) == 1
    captured = capsys.readouterr()
    assert captured.err == _READ_LINE
    _assert_secret_stays_hidden(captured)


def test_argument_wins_over_the_environment(tmp_path, monkeypatch, capsys):
    path = tmp_path / "wins.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, ticker VARCHAR(20) NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO companies (ticker) VALUES ('AAA')")
        )
    engine.dispose()
    monkeypatch.setenv("DATABASE_URL", _BAD_URL)
    assert main(["check", f"sqlite:///{path}"]) == 0
    captured = capsys.readouterr()
    _assert_secret_stays_hidden(captured)
    assert captured.out.strip() == "No duplicate tickers."


def test_tab_cr_and_lf_collide_without_rewriting(tmp_path, capsys):
    """Space-only TRIM would miss a tab, CR, or LF beside the symbol."""
    path = tmp_path / "ws.db"
    engine = create_engine(f"sqlite:///{path}")
    stored_values = ("AAPL\t", "aapl\r", "AAPL\n")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, ticker VARCHAR(20) NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO companies (id, ticker) VALUES "
                "(1, :tab), (2, :cr), (3, :lf)"
            ),
            {"tab": "AAPL\t", "cr": "aapl\r", "lf": "AAPL\n"},
        )
    engine.dispose()
    url = f"sqlite:///{path}"
    assert main(["check", url]) == 1
    error = capsys.readouterr().err
    for stored in stored_values:
        assert repr(stored) in error
    assert "did not change those rows" in error
    engine = create_engine(url)
    with engine.connect() as connection:
        assert duplicate_tickers(connection) == [
            ("AAPL", [("AAPL\t", 1), ("AAPL\n", 1), ("aapl\r", 1)])
        ]
        rows = (
            connection.execute(
                text("SELECT ticker FROM companies ORDER BY id")
            )
            .scalars()
            .all()
        )
        assert rows == ["AAPL\t", "aapl\r", "AAPL\n"]
    engine.dispose()


def test_script_prints_one_line_when_the_database_cannot_be_read(capsys):
    """A closed port is exit 1, not a traceback, and hides the password."""
    code = main(["check", "postgresql://u:secret@127.0.0.1:1/investment_test"])
    assert code == 1
    error = capsys.readouterr().err
    assert error == (
        "Could not read companies: the database is unreachable "
        "or the table is missing.\n"
    )
    assert "secret" not in error
    assert "Traceback" not in error


def test_bad_port_uses_the_fixed_url_line(capsys, monkeypatch):
    """A port that is not an integer is ``ValueError`` and exit 1.

    SQLAlchemy's parser raises before it connects. The fixed line
    replaces that message, which would otherwise name the bad port.
    The password in the URL is not printed.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    code = main(["check", "postgresql://u:secret@127.0.0.1:not-a-port/db"])
    assert code == 1
    captured = capsys.readouterr()
    assert captured.err == _URL_LINE
    assert captured.out == ""
    _assert_secret_stays_hidden(captured)
    assert "not-a-port" not in captured.err


def test_missing_driver_uses_the_fixed_url_line(capsys, monkeypatch):
    """``postgresql+psycopg`` is not installed, so connect raises ImportError.

    ``ModuleNotFoundError`` is a subclass of ``ImportError``. The fixed
    URL line replaces the driver text. The password is not printed.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    code = main(["check", "postgresql+psycopg://u:secret@127.0.0.1/db"])
    assert code == 1
    captured = capsys.readouterr()
    assert captured.err == _URL_LINE
    assert captured.out == ""
    _assert_secret_stays_hidden(captured)
    assert "psycopg" not in captured.err
    assert "ModuleNotFoundError" not in captured.err


def test_missing_sqlite_file_is_not_created(tmp_path, capsys, monkeypatch):
    """A mistyped SQLite path must not leave an empty file behind."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    path = tmp_path / "missing.db"
    code = main(["check", f"sqlite:///{path}"])
    assert code == 1
    captured = capsys.readouterr()
    assert "does not exist" in captured.err
    assert "no empty database file was created" in captured.err
    assert str(path) in captured.err
    assert captured.out == ""
    assert "Traceback" not in captured.err
    assert not path.exists()


def test_sqlite_uri_is_not_a_missing_file(tmp_path, capsys, monkeypatch):
    """An existing ``file:`` URI is read, not reported missing.

    The path after ``file:`` is checked the same way as a plain
    SQLite path. This file is already on disk, so the command
    reads it.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    path = tmp_path / "present.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, "
                "ticker VARCHAR(20) NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO companies (ticker) VALUES ('AAPL')")
        )
    engine.dispose()
    url = "sqlite:///file:" + path.as_posix() + "?mode=rw&uri=true"
    code = main(["check", url])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "No duplicate tickers.\n"
    assert captured.err == ""
    assert path.exists()


def test_percent_encoded_sqlite_uri_is_found(tmp_path, capsys, monkeypatch):
    """``%20`` in a ``file:`` URI is the space in the file name.

    ``mode=rw`` does not create a file. The command has to decode
    the path before it checks that the file exists, or it refuses
    a database that is already on disk.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    path = tmp_path / "x y.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, "
                "ticker VARCHAR(20) NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO companies (ticker) VALUES ('AAPL')")
        )
    engine.dispose()
    encoded = path.as_posix().replace(" ", "%20")
    url = "sqlite:///file:" + encoded + "?mode=rw&uri=true"
    code = main(["check", url])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "No duplicate tickers.\n"
    assert captured.err == ""
    assert path.exists()


def test_localhost_sqlite_uri_is_an_absolute_path(
    tmp_path, capsys, monkeypatch
):
    """``file://localhost/tmp/...`` is the absolute path ``/tmp/...``.

    ``localhost`` is the URI authority. Leaving it on the path
    would look for a relative file named ``localhost``.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    path = tmp_path / "local.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE companies ("
                "id INTEGER PRIMARY KEY, "
                "ticker VARCHAR(20) NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO companies (ticker) VALUES ('AAPL')")
        )
    engine.dispose()
    url = "sqlite:///file://localhost" + path.as_posix() + "?uri=true"
    code = main(["check", url])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "No duplicate tickers.\n"
    assert captured.err == ""
    assert path.exists()


def test_missing_sqlite_uri_is_not_created(tmp_path, capsys, monkeypatch):
    """A missing ``file:`` URI must not create an empty database.

    ``mode=rwc`` would create the file on connect. The command
    refuses first, with the same fixed line as a plain missing path.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    path = tmp_path / "missing-uri.db"
    urls = (
        "sqlite:///file:" + path.as_posix() + "?uri=true",
        "sqlite:///file:" + path.as_posix() + "?mode=rwc&uri=true",
    )
    for url in urls:
        code = main(["check", url])
        captured = capsys.readouterr()
        assert code == 1
        assert captured.err.startswith(
            "Could not read companies: the SQLite file does not exist, "
            "so no empty database file was created: "
        )
        assert path.as_posix() in captured.err
        assert captured.out == ""
        assert "Traceback" not in captured.err
        assert not path.exists()


def test_duplicate_tickers_requires_the_companies_table():
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        try:
            duplicate_tickers(connection)
        except CompaniesTableMissing as error:
            assert "companies" in str(error)
        else:
            raise AssertionError("missing table was accepted")
    engine.dispose()
