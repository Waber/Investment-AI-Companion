import pytest
import pytest_asyncio
from app.models.company import CompanyUpdate
from app.models.database_models import CompanyDB
from app.repositories.company_repository import CompanyRepository
from sqlalchemy.exc import IntegrityError


def snapshot(company):
    return {
        column.key: getattr(company, column.key)
        for column in CompanyDB.__table__.columns
    }


@pytest_asyncio.fixture
async def companies(client):
    records = []
    for name, ticker in [("First Corp", "FIRST"), ("Second Corp", "SECOND")]:
        response = await client.post(
            "/api/v1/companies/",
            json={
                "name": name,
                "ticker": ticker,
                "sector": "Technology",
                "industry": "Software",
                "description": f"Original {name}",
                "website": "https://example.com/",
                "country": "Poland",
                "exchange": "TEST",
                "currency": "PLN",
            },
        )
        assert response.status_code == 201
        records.append(response.json())
    return records


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["name", "ticker"])
async def test_duplicate_update_preserves_records(client, companies, field):
    first, second = companies
    url = f"/api/v1/companies/{first['id']}"
    with client.app.state.testing_session_local() as db:
        before = [snapshot(db.get(CompanyDB, c["id"])) for c in companies]

    response = await client.put(
        url,
        json={field: second[field], "description": "Must not be saved"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Company name or ticker already exists"
    for item in companies:
        fetched = await client.get(f"/api/v1/companies/{item['id']}")
        assert fetched.status_code == 200
        assert fetched.json() == item
    with client.app.state.testing_session_local() as db:
        after = [snapshot(db.get(CompanyDB, c["id"])) for c in companies]
        assert after == before

    replacement = "Renamed Corp" if field == "name" else "RENAMED"
    response = await client.put(url, json={field: replacement})
    assert response.status_code == 200
    assert response.json()[field] == replacement
    with client.app.state.testing_session_local() as db:
        stored = snapshot(db.get(CompanyDB, first["id"]))
        assert stored == {
            **before[0],
            field: replacement,
            "updated_at": stored["updated_at"],
        }
        assert snapshot(db.get(CompanyDB, second["id"])) == before[1]


@pytest.mark.asyncio
async def test_not_null_rollback_reuses_same_session(client, companies):
    first, second = companies
    with client.app.state.testing_session_local() as db:
        repo = CompanyRepository(db)
        original = repo.get_by_id(first["id"])
        other = repo.get_by_id(second["id"])
        before = [snapshot(original), snapshot(other)]

        with pytest.raises(
            ValueError, match="^Update failed due to constraint violation$"
        ) as error:
            repo.update(
                first["id"],
                CompanyUpdate(name=None, description="Must not be saved"),
            )

        # The repository wraps the real database error after rolling back.
        cause = error.value.__context__
        assert isinstance(cause, IntegrityError)
        assert "NOT NULL constraint failed: companies.name" in str(cause.orig)
        assert db.is_active
        assert [snapshot(original), snapshot(other)] == before

        updated = repo.update(first["id"], CompanyUpdate(name="Recovered"))
        assert repo.db is db
        db.expire_all()
        stored = snapshot(updated)
        assert stored == {
            **before[0],
            "name": "Recovered",
            "updated_at": stored["updated_at"],
        }
        assert snapshot(repo.get_by_id(second["id"])) == before[1]
