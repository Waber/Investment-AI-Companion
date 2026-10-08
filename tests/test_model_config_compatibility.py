"""Lock Pydantic and SQLAlchemy behavior while deprecated config is removed.

The response models can be built from SQLAlchemy rows or other attribute
objects, JSON fields stay the same, financial metrics still reject
Infinity and NaN, and the fetch-company schema keeps its ticker example.
A separate check treats the targeted deprecation warnings as errors.
"""

import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.data_collection import FetchCompanyRequest
from app.core.database import Base
from app.models import financial_metrics as fm
from app.models.company import Company
from app.models.database_models import CompanyDB, FinancialMetricsDB
from app.models.historical_data import HistoricalData
from main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OBSERVED_AT = datetime(2024, 6, 15, 12, 30, tzinfo=timezone.utc)
OBSERVED_AT_JSON = "2024-06-15T12:30:00Z"

COMPANY_VALUES = {
    "id": 7,
    "name": "Acme Corp",
    "ticker": "ACME",
    "sector": "Technology",
    "industry": "Software",
    "description": "Widget maker",
    "website": "https://example.com",
    "country": "USA",
    "exchange": "NASDAQ",
    "currency": "USD",
    "created_at": OBSERVED_AT,
    "updated_at": OBSERVED_AT,
    "is_active": True,
    "last_data_update": OBSERVED_AT,
}
COMPANY_JSON = {
    "name": "Acme Corp",
    "ticker": "ACME",
    "sector": "Technology",
    "industry": "Software",
    "description": "Widget maker",
    # The read model returns the stored string. It does not add a slash.
    "website": "https://example.com",
    "country": "USA",
    "exchange": "NASDAQ",
    "currency": "USD",
    "id": 7,
    "created_at": OBSERVED_AT_JSON,
    "updated_at": OBSERVED_AT_JSON,
    "is_active": True,
    "last_data_update": OBSERVED_AT_JSON,
}

METRIC_VALUES = {
    "id": 3,
    "company_id": 7,
    "period_end": OBSERVED_AT,
    "period_type": "annual",
    "revenue": 100.5,
    "net_income": 0.0,
    "total_assets": None,
    "total_liabilities": None,
    "total_equity": None,
    "roe": 0.16,
    "roa": None,
    "gross_margin": None,
    "net_margin": None,
    "current_ratio": None,
    "quick_ratio": None,
    "debt_to_equity": None,
    "debt_to_assets": None,
    "asset_turnover": None,
    "inventory_turnover": None,
    "revenue_growth": None,
    "net_income_growth": None,
    "pe_ratio": None,
    "pb_ratio": None,
    "ev_ebitda": None,
    "created_at": OBSERVED_AT,
    "updated_at": OBSERVED_AT,
}
METRIC_JSON = {
    "revenue": 100.5,
    "net_income": 0.0,
    "total_assets": None,
    "total_liabilities": None,
    "total_equity": None,
    "roe": 0.16,
    "roa": None,
    "gross_margin": None,
    "net_margin": None,
    "current_ratio": None,
    "quick_ratio": None,
    "debt_to_equity": None,
    "debt_to_assets": None,
    "asset_turnover": None,
    "inventory_turnover": None,
    "revenue_growth": None,
    "net_income_growth": None,
    "pe_ratio": None,
    "pb_ratio": None,
    "ev_ebitda": None,
    "id": 3,
    "company_id": 7,
    "period_end": OBSERVED_AT_JSON,
    "period_type": "annual",
    "created_at": OBSERVED_AT_JSON,
    "updated_at": OBSERVED_AT_JSON,
}

# There is no SQLAlchemy model for historical prices yet, so a plain
# attribute object stands in for a future row.
HISTORICAL_VALUES = {
    "id": 9,
    "company_id": 7,
    "date": OBSERVED_AT,
    "open_price": Decimal("10.50"),
    "high_price": Decimal("11.00"),
    "low_price": Decimal("10.00"),
    "close_price": Decimal("10.75"),
    "volume": 1000,
    "adjusted_close": Decimal("10.70"),
    "market_cap": None,
    "enterprise_value": None,
    "shares_outstanding": None,
    "avg_volume": None,
    "sma_20": None,
    "sma_50": None,
    "sma_200": None,
    "rsi_14": None,
    "macd": None,
    "macd_signal": None,
    "macd_hist": None,
    "created_at": OBSERVED_AT,
    "updated_at": OBSERVED_AT,
}
HISTORICAL_JSON = {
    "date": OBSERVED_AT_JSON,
    "open_price": "10.50",
    "high_price": "11.00",
    "low_price": "10.00",
    "close_price": "10.75",
    "volume": 1000,
    "adjusted_close": "10.70",
    "market_cap": None,
    "enterprise_value": None,
    "shares_outstanding": None,
    "avg_volume": None,
    "sma_20": None,
    "sma_50": None,
    "sma_200": None,
    "rsi_14": None,
    "macd": None,
    "macd_signal": None,
    "macd_hist": None,
    "id": 9,
    "company_id": 7,
    "created_at": OBSERVED_AT_JSON,
    "updated_at": OBSERVED_AT_JSON,
}

NONFINITE_VALUES = [
    float("inf"),
    float("-inf"),
    float("nan"),
    "Infinity",
    "-Infinity",
    "NaN",
]


def test_orm_models_keep_the_shared_declarative_base():
    assert CompanyDB.metadata is Base.metadata
    assert FinancialMetricsDB.metadata is Base.metadata
    assert {"companies", "financial_metrics"} <= set(Base.metadata.tables)


def test_response_models_read_attributes_and_reject_nonfinite_metrics():
    assert Company.model_config["from_attributes"] is True
    assert HistoricalData.model_config["from_attributes"] is True
    assert fm.FinancialMetrics.model_config["from_attributes"] is True
    assert fm.FinancialMetrics.model_config["allow_inf_nan"] is False
    for schema in (fm.FinancialMetricsCreate, fm.FinancialMetricsUpdate):
        assert schema.model_config["allow_inf_nan"] is False
        assert schema.model_config.get("from_attributes", False) is False


@pytest.mark.parametrize(
    "row_type",
    [SimpleNamespace, CompanyDB],
    ids=["attributes", "orm"],
)
def test_company_model_validate_serializes_response_fields(row_type):
    model = Company.model_validate(row_type(**COMPANY_VALUES))

    assert model.model_dump(mode="json") == COMPANY_JSON


@pytest.mark.parametrize(
    "row_type",
    [SimpleNamespace, FinancialMetricsDB],
    ids=["attributes", "orm"],
)
def test_metrics_model_validate_serializes_response_fields(row_type):
    model = fm.FinancialMetrics.model_validate(row_type(**METRIC_VALUES))

    assert model.model_dump(mode="json") == METRIC_JSON


def test_historical_model_validate_serializes_response_fields():
    model = HistoricalData.model_validate(SimpleNamespace(**HISTORICAL_VALUES))

    assert model.model_dump(mode="json") == HISTORICAL_JSON
    assert isinstance(model.open_price, Decimal)


@pytest.mark.parametrize(
    "value",
    NONFINITE_VALUES,
    ids=["inf", "-inf", "nan", "inf-str", "-inf-str", "nan-str"],
)
def test_financial_metrics_response_rejects_nonfinite_revenue(value):
    payload = dict(METRIC_VALUES)
    payload["revenue"] = value

    with pytest.raises(ValidationError) as exc_info:
        fm.FinancialMetrics.model_validate(payload)

    error = exc_info.value.errors()[0]
    assert error["loc"] == ("revenue",)
    assert error["type"] == "finite_number"


def test_financial_metrics_orm_row_rejects_nonfinite_revenue():
    values = dict(METRIC_VALUES)
    values["revenue"] = float("nan")

    with pytest.raises(ValidationError) as exc_info:
        fm.FinancialMetrics.model_validate(FinancialMetricsDB(**values))

    error = exc_info.value.errors()[0]
    assert error["loc"] == ("revenue",)
    assert error["type"] == "finite_number"


def test_fetch_company_request_keeps_ticker_schema_example():
    schema = FetchCompanyRequest.model_json_schema()

    assert schema["example"] == {"ticker": "AAPL"}
    assert "examples" not in schema
    assert schema["required"] == ["ticker"]
    assert schema["properties"]["ticker"]["type"] == "string"

    application = create_app(init_database_on_startup=False)
    spec = application.openapi()
    component = spec["components"]["schemas"]["FetchCompanyRequest"]
    assert component["example"] == {"ticker": "AAPL"}
    assert "examples" not in component

    schema_ref = {"$ref": "#/components/schemas/FetchCompanyRequest"}
    for path in (
        "/api/v1/data-collection/fetch-company",
        "/api/v1/data-collection/fetch-financial-metrics",
    ):
        body = spec["paths"][path]["post"]["requestBody"]
        assert body["content"]["application/json"]["schema"] == schema_ref


def test_project_imports_do_not_emit_targeted_deprecations(tmp_path):
    """Importing project models must not emit the deprecations we remove.

    A fresh interpreter is required. Python emits these warnings once,
    when the class or function is first defined.

    Settings reads `.env` from the process working directory. The child
    starts in a temporary directory, with a minimal environment, so a
    developer's `.env` in the repo root is not applied. The child checks
    that its working directory is not the project root. PYTHONPATH still
    points at this repository. This test does not write into the repo.
    """
    script = textwrap.dedent(r"""
        import os
        import warnings
        from pathlib import Path

        from pydantic.warnings import PydanticDeprecatedSince20
        from sqlalchemy.exc import MovedIn20Warning

        project_root = Path(os.environ["PYTHONPATH"]).resolve()
        if Path.cwd().resolve() == project_root:
            raise SystemExit(
                "warning check must not run from the project root"
            )

        # Match the start of the warning text. Python's filter is a
        # start-anchored regex, and these warnings are ignored by default
        # outside __main__ unless a filter promotes them to errors.
        warnings.filterwarnings(
            "error",
            message=(
                r"The ``declarative_base\(\)`` function is now available "
                r"as sqlalchemy\.orm\.declarative_base\(\)"
            ),
            category=MovedIn20Warning,
        )
        warnings.filterwarnings(
            "error",
            message=r"Support for class-based `config` is deprecated",
            category=PydanticDeprecatedSince20,
        )

        import app.api.data_collection
        import app.core.database
        import app.models.company
        import app.models.financial_metrics
        import app.models.historical_data
        """)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={
            "PATH": "/usr/bin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(PROJECT_ROOT),
            # The child imports Settings(), which requires this key.
            "SECRET_KEY": "unit-test-secret-key-0123456789abcd",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, (
        "Targeted deprecations were raised as errors.\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
