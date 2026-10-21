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
    """Driver text is not the message the operator sees."""
    from sqlalchemy.exc import SQLAlchemyError

    def explode(_url):
        raise SQLAlchemyError("driver text includes secret")

    monkeypatch.setattr(
        "scripts.check_duplicate_tickers.create_engine", explode
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert main(["check", "sqlite:///unused.db"]) == 1
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
    """An unreachable file is exit 1, not a traceback."""
    code = main(["check", "sqlite:////no/such/directory/companies.db"])
    assert code == 1
    error = capsys.readouterr().err
    assert error == (
        "Could not read companies: the database is unreachable "
        "or the table is missing.\n"
    )
    assert "Traceback" not in error


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
