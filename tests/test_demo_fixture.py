import json
from pathlib import Path

from app.models.company import CompanyCreate
from app.models.financial_metrics import FinancialMetricsCreate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "fixtures" / "demo-v1.json"


def test_demo_fixture_matches_current_api_and_database_limits():
    fixture = json.loads(FIXTURE_PATH.read_text())
    assert fixture["version"] == 1
    tickers = set()
    rows = 0
    for item in fixture["companies"]:
        company = CompanyCreate(**item["company"])
        assert company.ticker.startswith("DEMO_")
        assert len(company.ticker) <= 20
        assert company.ticker not in tickers
        tickers.add(company.ticker)
        assert company.description.startswith(fixture["marker"])
        assert len(company.currency) == 3
        periods = set()
        for raw in item["metrics"]:
            metrics = FinancialMetricsCreate(company_id=1, **raw)
            assert metrics.period_end.tzinfo is not None
            key = (metrics.period_type, metrics.period_end)
            assert key not in periods
            periods.add(key)
            values = (
                metrics.total_assets,
                metrics.total_liabilities,
                metrics.total_equity,
            )
            if all(value is not None for value in values):
                assert values[0] == values[1] + values[2]
            rows += 1
    assert len(tickers) == 6
    assert rows == 20


def test_demo_fixture_covers_ui_edge_cases_without_real_instruments():
    fixture = json.loads(FIXTURE_PATH.read_text())
    companies = fixture["companies"]
    metrics = [row for item in companies for row in item["metrics"]]
    assert any(not item["metrics"] for item in companies)
    assert any(item["company"]["website"] is None for item in companies)
    assert any(row["revenue"] == 0 for row in metrics)
    assert any(row["net_income"] is None for row in metrics)
    assert any((row["net_income"] or 0) < 0 for row in metrics)
    assert {row["period_type"] for row in metrics} == {"annual", "quarterly"}
    assert {item["company"]["currency"] for item in companies} == {
        "PLN",
        "USD",
        "EUR",
        "JPY",
        "SGD",
    }
