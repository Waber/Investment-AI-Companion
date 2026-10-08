"""Seed demo-v1 into a sqlite file without using the personal database."""

import json

import pytest
from sqlalchemy.orm import sessionmaker

from app.core import database
from app.core.config import settings
from app.core.database import Base, create_db_engine
from app.models.database_models import CompanyDB, FinancialMetricsDB
from scripts import seed_demo as seed


def test_apply_is_repeatable_and_leaves_settings_alone(tmp_path):
    database = tmp_path / "nested" / "investment_demo.db"
    url = f"sqlite:///{database}"
    before = settings.DATABASE_URL
    first = seed.seed_sqlite_database(url, apply=True)
    assert first["companies"]["created"] == 6
    assert first["metrics"]["created"] == 20
    assert database.is_file()
    second = seed.seed_sqlite_database(url, apply=True)
    assert second["companies"]["skipped"] == 6
    assert second["metrics"]["skipped"] == 20
    assert second["companies"]["created"] == 0
    assert settings.DATABASE_URL == before
    assert settings.DATABASE_URL != url

    engine = create_db_engine(url)
    try:
        session = sessionmaker(bind=engine)()
        try:
            assert session.query(CompanyDB).count() == 6
            assert session.query(FinancialMetricsDB).count() == 20
        finally:
            session.close()
    finally:
        engine.dispose()


def test_dry_run_creates_the_file_and_writes_no_rows(tmp_path):
    database = tmp_path / "dry.db"
    url = f"sqlite:///{database}"
    result = seed.seed_sqlite_database(url, apply=False)
    assert result["dry_run"] is True
    assert result["companies"]["pending"] == 6
    assert result["metrics"]["pending"] == 20
    engine = create_db_engine(url)
    try:
        session = sessionmaker(bind=engine)()
        try:
            assert session.query(CompanyDB).count() == 0
        finally:
            session.close()
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://investment_ai@localhost:5432/investment_ai",
        "sqlite://",
    ],
)
def test_non_sqlite_url_is_refused(url):
    with pytest.raises(ValueError):
        seed.seed_sqlite_database(url, apply=True)


def test_cli_database_url_calls_the_sqlite_helper(monkeypatch, capsys):
    seen = {}

    def fake(database_url, *, apply, fixture=None):
        seen["url"] = database_url
        seen["apply"] = apply
        return {"dry_run": not apply, "items": []}

    monkeypatch.setattr(seed, "seed_sqlite_database", fake)
    assert (
        seed.main(
            ["--database-url", "sqlite:///demo/investment_demo.db", "--apply"]
        )
        == 0
    )
    assert seen == {
        "url": "sqlite:///demo/investment_demo.db",
        "apply": True,
    }
    assert "dry_run" in json.loads(capsys.readouterr().out)


def test_cli_rejects_postgres_without_writing(capsys):
    code = seed.main(
        [
            "--database-url",
            "postgresql://investment_ai@localhost:5432/investment_ai",
        ]
    )
    assert code == 1
    assert "sqlite" in capsys.readouterr().err.casefold()


@pytest.mark.parametrize("url", ["not a url", "://nope"])
def test_unparseable_url_is_refused_without_echoing_it(url):
    with pytest.raises(
        ValueError, match="^Invalid database URL\\.$"
    ) as caught:
        seed._sqlite_file_url(url)
    assert url not in str(caught.value)


def test_memory_url_does_not_create_a_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert seed._sqlite_file_url("sqlite:///:memory:") == "sqlite:///:memory:"
    assert list(tmp_path.iterdir()) == []


def test_relative_sqlite_file_skips_mkdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert seed._sqlite_file_url("sqlite:///plain.db") == "sqlite:///plain.db"
    assert list(tmp_path.iterdir()) == []


def test_sqlite_client_rejects_an_unknown_request(tmp_path):
    url = f"sqlite:///{tmp_path / 'client.db'}"
    engine = create_db_engine(url)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        client = seed.SqliteSeedClient(session)
        with pytest.raises(ValueError, match="Unsupported seed request"):
            client.request("DELETE", "/api/v1/companies/")
    finally:
        session.close()
        engine.dispose()


def test_seed_stops_when_the_models_are_not_mapped(tmp_path, monkeypatch):
    class _EmptyMetadata:
        tables = {}

    monkeypatch.setattr(database.Base, "metadata", _EmptyMetadata())
    url = f"sqlite:///{tmp_path / 'missing.db'}"
    with pytest.raises(RuntimeError, match="missing tables"):
        seed.seed_sqlite_database(url, apply=False)


def test_cli_requires_one_target():
    with pytest.raises(SystemExit):
        seed.main([])
    with pytest.raises(SystemExit):
        seed.main(
            [
                "--base-url",
                "http://127.0.0.1:8081",
                "--database-url",
                "sqlite:///demo/investment_demo.db",
            ]
        )
