import pytest
import pytest_asyncio

from app.models.database_models import CompanyDB


@pytest_asyncio.fixture
async def company(client):
    response = await client.post(
        "/api/v1/companies/",
        json={
            "name": "Acme Corp",
            "ticker": "ACME",
            "description": "Original description",
            "website": "https://old.example.com",
        },
    )
    assert response.status_code == 201
    assert response.json()["website"] == "https://old.example.com/"
    return response.json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("website_update", "expected_website"),
    [
        pytest.param({}, "https://old.example.com/", id="omitted"),
        pytest.param(
            {"website": "https://NEW.example.com"},
            "https://new.example.com/",
            id="replacement-normalized",
        ),
        pytest.param({"website": None}, None, id="explicit-null"),
    ],
)
async def test_update_company_website(
    client, company, website_update, expected_website
):
    url = f"/api/v1/companies/{company['id']}"
    response = await client.put(
        url,
        json={"description": "Updated description", **website_update},
    )
    assert response.status_code == 200
    assert response.json()["website"] == expected_website
    assert response.json()["description"] == "Updated description"

    fetched = await client.get(url)
    assert fetched.status_code == 200
    assert fetched.json()["website"] == expected_website
    assert fetched.json()["description"] == "Updated description"

    with client.app.state.testing_session_local() as db:
        stored = db.get(CompanyDB, company["id"])
        assert stored.website == expected_website
        assert stored.description == "Updated description"
        if expected_website is not None:
            assert isinstance(stored.website, str)


@pytest.mark.asyncio
async def test_invalid_website_leaves_company_unchanged(client, company):
    url = f"/api/v1/companies/{company['id']}"
    with client.app.state.testing_session_local() as db:
        stored = db.get(CompanyDB, company["id"])
        before = {
            column.key: getattr(stored, column.key)
            for column in CompanyDB.__table__.columns
        }

    response = await client.put(
        url,
        json={
            "website": "not-a-url",
            "description": "Must not be saved",
        },
    )
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(error["loc"] == ["body", "website"] for error in errors)

    fetched = await client.get(url)
    assert fetched.status_code == 200
    assert fetched.json() == company

    with client.app.state.testing_session_local() as db:
        stored = db.get(CompanyDB, company["id"])
        after = {
            column.key: getattr(stored, column.key)
            for column in CompanyDB.__table__.columns
        }
        assert after == before
