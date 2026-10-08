"""SQLite timestamps, foreign keys, and demo-seed reruns (issues #23 and #20).

These tests check aware UTC timestamps, the app engine's SQLite foreign
keys, and a second demo-seed run. They do not use a live market-data
provider. The foreign-key test builds its own engine through
``app.core.database`` and does not use the ``client`` fixture.
"""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import seed_demo as seed
from tests.test_seed_demo import FakeClient, manifest

COMPANIES = "/api/v1/companies/"
METRICS = "/api/v1/financial-metrics/"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _explicit_utc(value):
    """Parse an API timestamp that must name UTC (``Z`` or ``+00:00``)."""
    assert value.endswith("Z") or value.endswith("+00:00"), value
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.utcoffset() == timedelta(0)
    return parsed


def _assert_aware_utc(value):
    assert value is not None
    assert value.tzinfo is not None and value.utcoffset() is not None
    assert value.utcoffset() == timedelta(0)


@pytest.mark.asyncio
async def test_sqlite_reads_timezone_aware_utc_for_every_datetime(client):
    """Company and metrics timestamps come back as UTC."""
    from app.models.database_models import CompanyDB, FinancialMetricsDB

    company = (
        await client.post(
            COMPANIES, json={"name": "UTC Co", "ticker": "UTCCO"}
        )
    ).json()
    created = await client.post(
        METRICS,
        json={
            "company_id": company["id"],
            "period_type": "annual",
            "period_end": "2025-12-31T02:00:00+02:00",
        },
    )
    assert created.status_code == 201, created.text

    # An offset that is not UTC must still be stored as that same instant.
    plus_two = timezone(timedelta(hours=2))
    written = datetime(2024, 6, 1, 3, 30, tzinfo=plus_two)
    session_factory = client.app.state.testing_session_local
    with session_factory() as db:
        row = db.get(CompanyDB, company["id"])
        row.last_data_update = written
        db.commit()

    with session_factory() as db:
        company_row = db.get(CompanyDB, company["id"])
        metrics_row = db.query(FinancialMetricsDB).one()
        for value in (
            company_row.created_at,
            company_row.updated_at,
            company_row.last_data_update,
            metrics_row.period_end,
            metrics_row.created_at,
            metrics_row.updated_at,
        ):
            _assert_aware_utc(value)
        assert metrics_row.period_end == datetime(
            2025, 12, 31, tzinfo=timezone.utc
        )
        assert company_row.last_data_update == datetime(
            2024, 6, 1, 1, 30, tzinfo=timezone.utc
        )


@pytest.mark.asyncio
async def test_api_returns_period_end_with_explicit_utc_offset(client):
    company = (
        await client.post(COMPANIES, json={"name": "Offset", "ticker": "OFFS"})
    ).json()
    created = await client.post(
        METRICS,
        json={
            "company_id": company["id"],
            "period_type": "annual",
            "period_end": "2025-12-31T02:00:00+02:00",
        },
    )
    assert created.status_code == 201, created.text
    assert _explicit_utc(created.json()["period_end"]) == datetime(
        2025, 12, 31, tzinfo=timezone.utc
    )

    listed = await client.get(f"{METRICS}company/{company['id']}")
    assert listed.status_code == 200
    assert _explicit_utc(listed.json()[0]["period_end"]) == datetime(
        2025, 12, 31, tzinfo=timezone.utc
    )


@pytest.mark.asyncio
async def test_naive_period_end_is_treated_as_utc(client):
    """Offsets-less input is UTC, matching timestamps the API already accepts.

    ``2024-12-31T00:00:00`` (no zone) is a current create payload in the
    suite. Treating it as UTC keeps that contract and makes it the same
    instant as ``...Z``. Rejecting it with 422 would be a breaking change.
    """
    company = (
        await client.post(COMPANIES, json={"name": "Naive", "ticker": "NAIV"})
    ).json()
    base = {"company_id": company["id"], "period_type": "annual"}
    created = await client.post(
        METRICS, json={**base, "period_end": "2025-06-30T00:00:00"}
    )
    assert created.status_code == 201, created.text
    assert _explicit_utc(created.json()["period_end"]) == datetime(
        2025, 6, 30, tzinfo=timezone.utc
    )

    duplicate = await client.post(
        METRICS, json={**base, "period_end": "2025-06-30T00:00:00Z"}
    )
    assert duplicate.status_code == 400


@pytest.mark.asyncio
async def test_update_normalizes_period_end_before_uniqueness_check(client):
    company = (
        await client.post(COMPANIES, json={"name": "Update", "ticker": "UPDT"})
    ).json()
    base = {"company_id": company["id"], "period_type": "annual"}
    first = await client.post(
        METRICS, json={**base, "period_end": "2025-12-31T00:00:00Z"}
    )
    second = await client.post(
        METRICS, json={**base, "period_end": "2024-12-31T00:00:00Z"}
    )
    assert first.status_code == second.status_code == 201

    # The same instant with another offset is the other row. PUT used to
    # ignore period_end; it now moves the period, and a collision is 400.
    conflict = await client.put(
        f"{METRICS}{second.json()['id']}",
        json={"period_end": "2025-12-31T02:00:00+02:00"},
    )
    assert conflict.status_code == 400
    unchanged = await client.get(f"{METRICS}{second.json()['id']}")
    assert unchanged.status_code == 200
    assert _explicit_utc(unchanged.json()["period_end"]) == datetime(
        2024, 12, 31, tzinfo=timezone.utc
    )

    moved = await client.put(
        f"{METRICS}{second.json()['id']}",
        json={"period_end": "2023-06-30T00:00:00Z"},
    )
    assert moved.status_code == 200, moved.text
    assert _explicit_utc(moved.json()["period_end"]) == datetime(
        2023, 6, 30, tzinfo=timezone.utc
    )

    shifted = await client.put(
        f"{METRICS}{second.json()['id']}",
        json={"period_end": "2023-06-30T02:00:00+02:00"},
    )
    assert shifted.status_code == 200, shifted.text
    assert _explicit_utc(shifted.json()["period_end"]) == datetime(
        2023, 6, 30, tzinfo=timezone.utc
    )


@pytest.mark.asyncio
async def test_update_rejects_null_period_end_and_keeps_omitted(client):
    """Explicit null is 422. Leaving the field out does not clear it.

    On master, ``PUT`` with ``period_end: null`` returned 200 and the
    value was ignored. At ``c3c8911`` the model accepted null, and the
    database NOT NULL check came back as 400 ``constraint violation``.
    """
    company = (
        await client.post(COMPANIES, json={"name": "Null", "ticker": "NULLP"})
    ).json()
    created = await client.post(
        METRICS,
        json={
            "company_id": company["id"],
            "period_type": "annual",
            "period_end": "2025-12-31T00:00:00Z",
            "revenue": 1.0,
        },
    )
    assert created.status_code == 201, created.text
    metrics_id = created.json()["id"]
    original = created.json()["period_end"]

    rejected = await client.put(
        f"{METRICS}{metrics_id}", json={"period_end": None}
    )
    assert rejected.status_code == 422, rejected.text
    errors = rejected.json()["detail"]
    assert any(error["loc"] == ["body", "period_end"] for error in errors)

    still_there = await client.get(f"{METRICS}{metrics_id}")
    assert still_there.status_code == 200
    assert still_there.json()["period_end"] == original

    omitted = await client.put(f"{METRICS}{metrics_id}", json={"revenue": 4.5})
    assert omitted.status_code == 200, omitted.text
    assert omitted.json()["period_end"] == original
    assert omitted.json()["revenue"] == 4.5


def test_put_period_end_schema_is_not_nullable():
    """PUT documents period_end as a date-time, not as null."""
    from main import create_app

    spec = create_app(init_database_on_startup=False).openapi()
    operation = spec["paths"]["/api/v1/financial-metrics/{metrics_id}"]["put"]
    body = operation["requestBody"]["content"]["application/json"]["schema"]
    name = body["$ref"].rsplit("/", 1)[-1]
    schema = spec["components"]["schemas"][name]
    period_end = schema["properties"]["period_end"]

    assert period_end["type"] == "string"
    assert period_end["format"] == "date-time"
    assert "anyOf" not in period_end
    assert period_end.get("nullable") is not True
    assert "default" not in period_end
    assert "period_end" not in schema.get("required", [])


def test_app_engine_enforces_sqlite_foreign_keys(tmp_path):
    """Orphan metrics fail on the app engine, not the test hook."""
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import sessionmaker

    from app.core import database
    from app.models.database_models import FinancialMetricsDB

    assert hasattr(database, "create_db_engine")
    engine = database.create_db_engine(f"sqlite:///{tmp_path / 'fk.db'}")
    database.Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False)

    def foreign_keys_flag():
        with engine.connect() as connection:
            return connection.exec_driver_sql("PRAGMA foreign_keys").scalar()

    assert foreign_keys_flag() == 1
    engine.dispose()
    assert foreign_keys_flag() == 1

    with session_factory() as db:
        db.add(
            FinancialMetricsDB(
                company_id=999,
                period_end=datetime(2025, 12, 31, tzinfo=timezone.utc),
                period_type="annual",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
    engine.dispose()


def test_postgres_engine_does_not_attach_sqlite_foreign_key_hook(monkeypatch):
    """A PostgreSQL URL gets no SQLite listener and opens no connection."""
    import psycopg2
    from sqlalchemy import event

    from app.core import database

    def refuse_connect(*args, **kwargs):
        raise AssertionError("create_db_engine opened a connection")

    monkeypatch.setattr(psycopg2, "connect", refuse_connect)
    engine = database.create_db_engine("postgresql://u@localhost/x")
    try:
        assert engine.dialect.name == "postgresql"
        assert not event.contains(
            engine, "connect", database.enable_sqlite_foreign_keys
        )
        assert engine.pool.checkedout() == 0
        assert engine.pool.checkedin() == 0
    finally:
        engine.dispose()


def test_utc_datetime_type_normalizes_sqlite_without_changing_postgres():
    """SQLite stores a UTC wall clock. PostgreSQL stays aware."""
    from app.core.utc_datetime import UTCDateTime

    column = UTCDateTime()
    assert column.cache_ok is True
    plus_two = timezone(timedelta(hours=2))
    aware = datetime(2025, 12, 31, 2, 0, tzinfo=plus_two)
    naive_utc_wall = datetime(2025, 12, 31, 0, 0)
    utc = datetime(2025, 12, 31, 0, 0, tzinfo=timezone.utc)

    class _Dialect:
        def __init__(self, name):
            self.name = name

    sqlite = _Dialect("sqlite")
    postgres = _Dialect("postgresql")

    stored = column.process_bind_param(aware, sqlite)
    assert stored == naive_utc_wall
    assert stored.tzinfo is None
    assert column.process_bind_param(naive_utc_wall, sqlite) == naive_utc_wall
    assert column.process_result_value(naive_utc_wall, sqlite) == utc
    assert column.process_bind_param(None, sqlite) is None
    assert column.process_result_value(None, sqlite) is None

    bound = column.process_bind_param(aware, postgres)
    assert bound == utc
    assert bound.tzinfo is not None
    assert column.process_bind_param(naive_utc_wall, postgres) == utc
    assert column.process_result_value(utc, postgres) == utc
    assert column.process_result_value(aware, postgres) == utc
    assert column.process_bind_param(None, postgres) is None
    assert column.process_result_value(None, postgres) is None


def test_seed_treats_naive_sqlite_period_end_as_the_same_instant():
    """A rerun must skip rows whose period_end lost its offset on SQLite."""
    fixture, client = manifest(), FakeClient()
    seed.seed_demo(fixture, client, apply=True)
    client.metrics[0]["period_end"] = "2025-12-31T00:00:00"

    result = seed.seed_demo(fixture, client, apply=True)

    assert result["metrics"] == {"created": 0, "skipped": 2, "pending": 0}
    assert result["companies"]["created"] == 0


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(base_url, proc, log_path):
    deadline = time.time() + 20
    last_error = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            log = log_path.read_text(encoding="utf-8", errors="replace")
            raise AssertionError(
                f"API exited {proc.returncode} before it was ready:\n{log}"
            )
        try:
            with urllib.request.urlopen(
                base_url + "/", timeout=0.5
            ) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = str(exc)
        time.sleep(0.1)
    log = log_path.read_text(encoding="utf-8", errors="replace")
    raise AssertionError(f"API did not start ({last_error}):\n{log}")


def test_seed_demo_apply_twice_on_fresh_sqlite(tmp_path):
    """``python scripts/seed_demo.py --apply`` is safe to run twice.

    ``--base-url`` is required by the script. ``PYTHONPATH`` is the repo
    root so ``import scripts`` works when the file is executed directly.
    """
    database_path = tmp_path / "demo.db"
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    log_path = tmp_path / "server.log"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["DATABASE_URL"] = f"sqlite:///{database_path}"

    with log_path.open("w", encoding="utf-8") as log_handle:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=REPO_ROOT,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_for_server(base_url, proc, log_path)
            summaries = []
            for _ in range(2):
                completed = subprocess.run(
                    [
                        sys.executable,
                        "scripts/seed_demo.py",
                        "--base-url",
                        base_url,
                        "--apply",
                    ],
                    cwd=REPO_ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                assert completed.returncode == 0, (
                    completed.stderr + "\n" + completed.stdout
                )
                summaries.append(json.loads(completed.stdout))
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

    assert summaries[0]["companies"]["created"] == 6
    assert summaries[0]["metrics"]["created"] == 20
    assert summaries[1]["companies"] == {
        "created": 0,
        "skipped": 6,
        "pending": 0,
    }
    assert summaries[1]["metrics"] == {
        "created": 0,
        "skipped": 20,
        "pending": 0,
    }

    connection = sqlite3.connect(database_path)
    try:
        companies = connection.execute(
            "select count(*) from companies"
        ).fetchone()
        metrics = connection.execute(
            "select count(*) from financial_metrics"
        ).fetchone()
        duplicates = connection.execute("""
            select count(*) from (
                select company_id, period_end, period_type
                from financial_metrics
                group by company_id, period_end, period_type
                having count(*) > 1
            )
            """).fetchone()
    finally:
        connection.close()
    assert companies[0] == 6
    assert metrics[0] == 20
    assert duplicates[0] == 0
