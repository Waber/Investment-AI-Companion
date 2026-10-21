"""The preflight that revision 0002 runs before it adds an index."""

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


def test_script_rejects_a_missing_table_and_a_missing_url(tmp_path, capsys):
    path = tmp_path / "empty.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE other (id INTEGER)"))
    engine.dispose()

    assert main(["check", f"sqlite:///{path}"]) == 2
    assert "companies table is not in this database" in capsys.readouterr().err

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
