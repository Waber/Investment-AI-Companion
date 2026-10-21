import pytest
from pydantic import ValidationError

from app.models.company import CompanyCreate, CompanyUpdate
from app.models.database_models import CompanyDB


def test_name_is_stripped_and_a_blank_name_is_rejected():
    created = CompanyCreate(name="  Acme  ", ticker="AAA")
    updated = CompanyUpdate(name="  New  ")

    assert created.name == "Acme"
    assert updated.name == "New"
    assert "name" not in CompanyUpdate().model_dump(exclude_unset=True)
    with pytest.raises(ValidationError):
        CompanyCreate(name="   ", ticker="AAA")
    with pytest.raises(ValidationError):
        CompanyUpdate(name=" ")
    for invisible in ("\u200b", "\ufeff", "\u200c\u200d", "  \u200b  "):
        with pytest.raises(ValidationError):
            CompanyCreate(name=invisible, ticker="AAA")
        with pytest.raises(ValidationError):
            CompanyUpdate(name=invisible)
    # After strip, a name with no character outside whitespace and
    # Unicode category C* is blank. Cc is a control, Cf is format,
    # Co is private use, Cn is unassigned. A letter next to a format
    # character is a real name and is kept.
    for invisible in (
        "\u200b \u200b",
        "\x00",
        "\ue000",
        "\u0378",
        "\x00 \ue000",
    ):
        with pytest.raises(ValidationError):
            CompanyCreate(name=invisible, ticker="AAA")
        with pytest.raises(ValidationError):
            CompanyUpdate(name=invisible)
    kept = CompanyCreate(name="Acme\u200b", ticker="AAA")
    assert kept.name == "Acme\u200b"
    beside = CompanyCreate(name="A\u200bB", ticker="AAA")
    assert beside.name == "A\u200bB"


@pytest.mark.asyncio
async def test_blank_name_is_422_on_create_and_update(client):
    created = await client.post(
        "/api/v1/companies/", json={"name": "  Kept  ", "ticker": "KEEP"}
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Kept"
    company_id = created.json()["id"]

    blank_create = await client.post(
        "/api/v1/companies/", json={"name": "   ", "ticker": "BLANK"}
    )
    assert blank_create.status_code == 422
    assert "name" in blank_create.text

    blank_update = await client.put(
        f"/api/v1/companies/{company_id}", json={"name": " "}
    )
    assert blank_update.status_code == 422
    fetched = await client.get(f"/api/v1/companies/{company_id}")
    assert fetched.json()["name"] == "Kept"

    renamed = await client.put(
        f"/api/v1/companies/{company_id}", json={"name": "  Renamed  "}
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renamed"

    for invisible in ("\u200b \u200b", "\x00", "\ue000"):
        rejected = await client.post(
            "/api/v1/companies/", json={"name": invisible, "ticker": "INVIS"}
        )
        assert rejected.status_code == 422
        rejected_update = await client.put(
            f"/api/v1/companies/{company_id}", json={"name": invisible}
        )
        assert rejected_update.status_code == 422
    fetched = await client.get(f"/api/v1/companies/{company_id}")
    assert fetched.json()["name"] == "Renamed"
    kept = await client.put(
        f"/api/v1/companies/{company_id}", json={"name": "A\u200bB"}
    )
    assert kept.status_code == 200
    assert kept.json()["name"] == "A\u200bB"

    db = client.app.state.testing_session_local()
    try:
        assert db.query(CompanyDB).count() == 1
        assert db.get(CompanyDB, company_id).name == "A\u200bB"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_create_and_list_company_persists_website_as_string(client):
    payload = {
        "name": "Acme Corp",
        "ticker": "ACME",
        "sector": "Technology",
        "industry": "Software",
        "website": "https://example.com",
        "country": "USA",
        "exchange": "NASDAQ",
        "currency": "USD",
    }

    create_response = await client.post("/api/v1/companies/", json=payload)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["ticker"] == "ACME"
    assert created["website"] == "https://example.com/"

    list_response = await client.get("/api/v1/companies/")

    assert list_response.status_code == 200
    companies = list_response.json()
    assert len(companies) == 1
    assert companies[0]["website"] == "https://example.com/"

    db = client.app.state.testing_session_local()
    try:
        stored = db.query(CompanyDB).filter(CompanyDB.ticker == "ACME").one()
        assert stored.website == "https://example.com/"
        assert isinstance(stored.website, str)
    finally:
        db.close()
