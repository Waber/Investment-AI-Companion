"""Create, edit, and delete forms for companies and their metrics.

HTML forms only send GET and POST, so an edit is a POST and not a PUT.
The path is still under /ui. HTMX is not required: a 4xx response is
the whole form again, and HTMX does not swap error pages unless the
shared htmx-config meta is changed. The list filter keeps using HTMX.

Successful posts answer 303 and send the browser to a GET page, so a
refresh does not save a second time. Invalid input is 422. A
repository ValueError (a duplicate) is 400. Both render the same form
with the user's text still in the fields. A bad id uses the same guard
as the detail page and is the HTML 404.

Deleting a company goes through ``CompanyRepository.delete``. The
company relationship cascades to financial metrics. Prices, a
watchlist, notes, and analyses are not stored on this model.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.company_repository import CompanyRepository
from app.repositories.financial_metrics_repository import (
    FinancialMetricsRepository,
)
from app.ui.form_fields import (
    COMPANY_FIELDS,
    blank_company,
    blank_metrics,
    catalog_key_for_repository_error,
    company_values,
    described_by,
    field_label_key,
    metrics_values,
    validate_company,
    validate_metrics,
)
from app.ui.origin import require_same_origin
from app.ui.router import _instrument_id, _with_ui_headers
from app.ui.templating import render
from app.ui.view_models import METRIC_FIELDS

router = APIRouter(
    prefix="/ui",
    tags=["ui"],
    dependencies=[Depends(require_same_origin)],
)

_COMPANY_HINTS = {}
_METRIC_HINTS = {field: "hint-numbers" for field in METRIC_FIELDS}
_METRIC_HINTS["period_end"] = "hint-period_end"
_METRIC_HINTS["period_type"] = "hint-period_type"


def posted_company(
    name: str = Form(""),
    ticker: str = Form(""),
    exchange: str = Form(""),
    currency: str = Form(""),
    country: str = Form(""),
    sector: str = Form(""),
    industry: str = Form(""),
    website: str = Form(""),
    description: str = Form(""),
):
    """Posted company fields. Defaults keep a missing key from being 500."""
    return {
        "name": name,
        "ticker": ticker,
        "exchange": exchange,
        "currency": currency,
        "country": country,
        "sector": sector,
        "industry": industry,
        "website": website,
        "description": description,
    }


def posted_metrics(
    period_end: str = Form(""),
    period_type: str = Form(""),
    revenue: str = Form(""),
    net_income: str = Form(""),
    total_assets: str = Form(""),
    total_liabilities: str = Form(""),
    total_equity: str = Form(""),
    roe: str = Form(""),
    roa: str = Form(""),
    gross_margin: str = Form(""),
    net_margin: str = Form(""),
    current_ratio: str = Form(""),
    quick_ratio: str = Form(""),
    debt_to_equity: str = Form(""),
    debt_to_assets: str = Form(""),
    asset_turnover: str = Form(""),
    inventory_turnover: str = Form(""),
    revenue_growth: str = Form(""),
    net_income_growth: str = Form(""),
    pe_ratio: str = Form(""),
    pb_ratio: str = Form(""),
    ev_ebitda: str = Form(""),
):
    """Posted metric fields. ``period_type`` is ignored on update."""
    return {
        "period_end": period_end,
        "period_type": period_type,
        "revenue": revenue,
        "net_income": net_income,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "roe": roe,
        "roa": roa,
        "gross_margin": gross_margin,
        "net_margin": net_margin,
        "current_ratio": current_ratio,
        "quick_ratio": quick_ratio,
        "debt_to_equity": debt_to_equity,
        "debt_to_assets": debt_to_assets,
        "asset_turnover": asset_turnover,
        "inventory_turnover": inventory_turnover,
        "revenue_growth": revenue_growth,
        "net_income_growth": net_income_growth,
        "pe_ratio": pe_ratio,
        "pb_ratio": pb_ratio,
        "ev_ebitda": ev_ebitda,
    }


def _see_other(url):
    """303 so the next request is a GET. A refresh does not re-post."""
    return _with_ui_headers(RedirectResponse(url, status_code=303))


def _not_found(request):
    return _with_ui_headers(render(request, "not_found.html", status_code=404))


def _load_company(request, db, raw_id):
    """Return ``(row, response)``. One of the two is None."""
    parsed = _instrument_id(raw_id)
    if parsed is None:
        return None, _not_found(request)
    row = CompanyRepository(db).get_by_id(parsed)
    if row is None:
        return None, _not_found(request)
    return row, None


def _load_metrics(request, db, company_raw, metrics_raw):
    """Return ``(company, metrics, response)``."""
    company, missing = _load_company(request, db, company_raw)
    if missing is not None:
        return None, None, missing
    parsed = _instrument_id(metrics_raw)
    if parsed is None:
        return None, None, _not_found(request)
    row = FinancialMetricsRepository(db).get_by_id(parsed)
    if row is None or row.company_id != company.id:
        return None, None, _not_found(request)
    return company, row, None


def _descriptions(fields, errors, form_error, invalid_fields, hints):
    return {
        field: described_by(field, errors, form_error, invalid_fields, hints)
        for field in fields
    }


def _company_page(
    request,
    *,
    title_key,
    action,
    values,
    cancel_href,
    updated_at=None,
    errors=None,
    form_error=None,
    invalid_fields=None,
    status_code=200,
):
    errors = errors or {}
    invalid = tuple(invalid_fields or ())
    return _with_ui_headers(
        render(
            request,
            "company_form.html",
            status_code=status_code,
            title_key=title_key,
            action=action,
            values=values,
            cancel_href=cancel_href,
            updated_at=updated_at,
            errors=errors,
            form_error=form_error,
            invalid_fields=invalid,
            described_by=_descriptions(
                COMPANY_FIELDS, errors, form_error, invalid, _COMPANY_HINTS
            ),
            company_fields=COMPANY_FIELDS,
            field_label_key=field_label_key,
        )
    )


def _metrics_page(
    request,
    *,
    title_key,
    action,
    values,
    cancel_href,
    period_type_locked,
    updated_at=None,
    errors=None,
    form_error=None,
    invalid_fields=None,
    status_code=200,
):
    errors = errors or {}
    invalid = tuple(invalid_fields or ())
    fields = ("period_end", "period_type") + METRIC_FIELDS
    return _with_ui_headers(
        render(
            request,
            "metrics_form.html",
            status_code=status_code,
            title_key=title_key,
            action=action,
            values=values,
            cancel_href=cancel_href,
            period_type_locked=period_type_locked,
            updated_at=updated_at,
            errors=errors,
            form_error=form_error,
            invalid_fields=invalid,
            described_by=_descriptions(
                fields, errors, form_error, invalid, _METRIC_HINTS
            ),
            metric_fields=METRIC_FIELDS,
            field_label_key=field_label_key,
        )
    )


def _confirm_page(
    request,
    *,
    title_key,
    warning_key,
    question_key,
    action,
    cancel_href,
    company_name,
    period_end=None,
    period_type=None,
):
    return _with_ui_headers(
        render(
            request,
            "confirm_delete.html",
            title_key=title_key,
            warning_key=warning_key,
            question_key=question_key,
            action=action,
            cancel_href=cancel_href,
            company_name=company_name,
            period_end=period_end,
            period_type=period_type,
        )
    )


def _company_invalid(
    request,
    values,
    errors,
    form_error,
    *,
    title_key,
    action,
    cancel_href,
    updated_at=None,
):
    invalid = tuple(errors)
    return _company_page(
        request,
        title_key=title_key,
        action=action,
        values=values,
        cancel_href=cancel_href,
        updated_at=updated_at,
        errors=errors,
        form_error=form_error,
        invalid_fields=invalid,
        status_code=422,
    )


def _company_conflict(
    request,
    values,
    key,
    *,
    title_key,
    action,
    cancel_href,
    updated_at=None,
):
    # Name and ticker are the two columns the repository treats as
    # unique. The summary links to both; the message says "or".
    return _company_page(
        request,
        title_key=title_key,
        action=action,
        values=values,
        cancel_href=cancel_href,
        updated_at=updated_at,
        form_error=key,
        invalid_fields=("name", "ticker"),
        status_code=400,
    )


def _save_company(db, model, *, update, company_id):
    """Return the saved row, or raise ValueError / IntegrityError."""
    repo = CompanyRepository(db)
    if update:
        return repo.update(company_id, model)
    return repo.create(model)


@router.get("/companies/new", include_in_schema=False)
def new_company_form(request: Request):
    """Empty create form. GET does not insert a row."""
    return _company_page(
        request,
        title_key="page.create_company",
        action="/ui/companies",
        values=blank_company(),
        cancel_href="/ui",
    )


@router.post("/companies", include_in_schema=False)
def create_company(
    request: Request,
    values: dict = Depends(posted_company),
    db: Session = Depends(get_db),
):
    """Validate with CompanyCreate and insert through the repository."""
    model, errors, form_error = validate_company(values, update=False)
    if model is None:
        return _company_invalid(
            request,
            values,
            errors,
            form_error,
            title_key="page.create_company",
            action="/ui/companies",
            cancel_href="/ui",
        )
    try:
        row = _save_company(db, model, update=False, company_id=None)
    except ValueError as exc:
        return _company_conflict(
            request,
            values,
            catalog_key_for_repository_error(exc),
            title_key="page.create_company",
            action="/ui/companies",
            cancel_href="/ui",
        )
    except IntegrityError:
        # The ticker column is unique on its own. The repository turns
        # the (name, ticker) constraint into ValueError and re-raises
        # the ticker-only failure. Show that as a duplicate, not a 500.
        db.rollback()
        return _company_conflict(
            request,
            values,
            "error.duplicate_company",
            title_key="page.create_company",
            action="/ui/companies",
            cancel_href="/ui",
        )
    return _see_other(f"/ui/instruments/{row.id}")


@router.get("/companies/{company_id}/edit", include_in_schema=False)
def edit_company_form(
    request: Request, company_id: str, db: Session = Depends(get_db)
):
    """Edit form filled from the stored row."""
    row, missing = _load_company(request, db, company_id)
    if missing is not None:
        return missing
    return _company_page(
        request,
        title_key="page.edit_company",
        action=f"/ui/companies/{row.id}/edit",
        values=company_values(row),
        cancel_href=f"/ui/instruments/{row.id}",
        updated_at=row.updated_at,
    )


@router.post("/companies/{company_id}/edit", include_in_schema=False)
def update_company(
    request: Request,
    company_id: str,
    values: dict = Depends(posted_company),
    db: Session = Depends(get_db),
):
    """Validate with CompanyUpdate. Every field on the form is sent."""
    row, missing = _load_company(request, db, company_id)
    if missing is not None:
        return missing
    model, errors, form_error = validate_company(values, update=True)
    page = {
        "title_key": "page.edit_company",
        "action": f"/ui/companies/{row.id}/edit",
        "cancel_href": f"/ui/instruments/{row.id}",
        "updated_at": row.updated_at,
    }
    if model is None:
        return _company_invalid(request, values, errors, form_error, **page)
    try:
        saved = _save_company(db, model, update=True, company_id=row.id)
    except ValueError as exc:
        return _company_conflict(
            request,
            values,
            catalog_key_for_repository_error(exc),
            **page,
        )
    except IntegrityError:
        db.rollback()
        return _company_conflict(
            request, values, "error.duplicate_company", **page
        )
    if saved is None:
        return _not_found(request)
    return _see_other(f"/ui/instruments/{saved.id}")


@router.get("/companies/{company_id}/delete", include_in_schema=False)
def delete_company_form(
    request: Request, company_id: str, db: Session = Depends(get_db)
):
    """Confirmation only. The row is still there after this GET."""
    row, missing = _load_company(request, db, company_id)
    if missing is not None:
        return missing
    return _confirm_page(
        request,
        title_key="page.delete_company",
        warning_key="delete.company_warning",
        question_key="delete.company_question",
        action=f"/ui/companies/{row.id}/delete",
        cancel_href=f"/ui/instruments/{row.id}",
        company_name=row.name,
    )


@router.post("/companies/{company_id}/delete", include_in_schema=False)
def delete_company(
    request: Request, company_id: str, db: Session = Depends(get_db)
):
    """Delete the company. Related financial metrics go with it."""
    row, missing = _load_company(request, db, company_id)
    if missing is not None:
        return missing
    CompanyRepository(db).delete(row.id)
    return _see_other("/ui")


@router.get("/companies/{company_id}/metrics/new", include_in_schema=False)
def new_metrics_form(
    request: Request, company_id: str, db: Session = Depends(get_db)
):
    """Empty metrics form for one company."""
    row, missing = _load_company(request, db, company_id)
    if missing is not None:
        return missing
    return _metrics_page(
        request,
        title_key="page.create_metrics",
        action=f"/ui/companies/{row.id}/metrics",
        values=blank_metrics(),
        cancel_href=f"/ui/instruments/{row.id}",
        period_type_locked=False,
    )


def _metrics_invalid(
    request,
    company,
    values,
    errors,
    form_error,
    *,
    update,
    metrics_id,
    updated_at=None,
):
    if update:
        action = f"/ui/companies/{company.id}/metrics/{metrics_id}/edit"
        title_key = "page.edit_metrics"
    else:
        action = f"/ui/companies/{company.id}/metrics"
        title_key = "page.create_metrics"
    return _metrics_page(
        request,
        title_key=title_key,
        action=action,
        values=values,
        cancel_href=f"/ui/instruments/{company.id}",
        period_type_locked=update,
        updated_at=updated_at,
        errors=errors,
        form_error=form_error,
        invalid_fields=tuple(errors),
        status_code=422,
    )


def _metrics_conflict(
    request,
    company,
    values,
    key,
    *,
    update,
    metrics_id,
    updated_at=None,
):
    if update:
        action = f"/ui/companies/{company.id}/metrics/{metrics_id}/edit"
        title_key = "page.edit_metrics"
        invalid = ("period_end",)
    else:
        action = f"/ui/companies/{company.id}/metrics"
        title_key = "page.create_metrics"
        invalid = ("period_end", "period_type")
    return _metrics_page(
        request,
        title_key=title_key,
        action=action,
        values=values,
        cancel_href=f"/ui/instruments/{company.id}",
        period_type_locked=update,
        updated_at=updated_at,
        form_error=key,
        invalid_fields=invalid,
        status_code=400,
    )


@router.post("/companies/{company_id}/metrics", include_in_schema=False)
def create_metrics(
    request: Request,
    company_id: str,
    values: dict = Depends(posted_metrics),
    db: Session = Depends(get_db),
):
    """Validate with FinancialMetricsCreate for this company only."""
    company, missing = _load_company(request, db, company_id)
    if missing is not None:
        return missing
    model, errors, form_error = validate_metrics(
        values, company.id, update=False
    )
    if model is None:
        return _metrics_invalid(
            request,
            company,
            values,
            errors,
            form_error,
            update=False,
            metrics_id=None,
        )
    repo = FinancialMetricsRepository(db)
    try:
        repo.create(model)
    except ValueError as exc:
        return _metrics_conflict(
            request,
            company,
            values,
            catalog_key_for_repository_error(exc),
            update=False,
            metrics_id=None,
        )
    except IntegrityError:
        db.rollback()
        return _metrics_conflict(
            request,
            company,
            values,
            "error.constraint",
            update=False,
            metrics_id=None,
        )
    return _see_other(f"/ui/instruments/{company.id}")


@router.get(
    "/companies/{company_id}/metrics/{metrics_id}/edit",
    include_in_schema=False,
)
def edit_metrics_form(
    request: Request,
    company_id: str,
    metrics_id: str,
    db: Session = Depends(get_db),
):
    """Edit one period. The period type is shown and not submitted."""
    company, row, missing = _load_metrics(request, db, company_id, metrics_id)
    if missing is not None:
        return missing
    return _metrics_page(
        request,
        title_key="page.edit_metrics",
        action=f"/ui/companies/{company.id}/metrics/{row.id}/edit",
        values=metrics_values(row),
        cancel_href=f"/ui/instruments/{company.id}",
        period_type_locked=True,
        updated_at=row.updated_at,
    )


@router.post(
    "/companies/{company_id}/metrics/{metrics_id}/edit",
    include_in_schema=False,
)
def update_metrics(
    request: Request,
    company_id: str,
    metrics_id: str,
    values: dict = Depends(posted_metrics),
    db: Session = Depends(get_db),
):
    """Validate with FinancialMetricsUpdate. Period type stays put."""
    company, row, missing = _load_metrics(request, db, company_id, metrics_id)
    if missing is not None:
        return missing
    # The update model ignores period_type. Keep the stored value in
    # the form so a failed post does not blank the read-only line.
    values = dict(values)
    values["period_type"] = row.period_type or ""
    model, errors, form_error = validate_metrics(
        values, company.id, update=True
    )
    if model is None:
        return _metrics_invalid(
            request,
            company,
            values,
            errors,
            form_error,
            update=True,
            metrics_id=row.id,
            updated_at=row.updated_at,
        )
    repo = FinancialMetricsRepository(db)
    try:
        saved = repo.update(row.id, model)
    except ValueError as exc:
        return _metrics_conflict(
            request,
            company,
            values,
            catalog_key_for_repository_error(exc),
            update=True,
            metrics_id=row.id,
            updated_at=row.updated_at,
        )
    except IntegrityError:
        db.rollback()
        return _metrics_conflict(
            request,
            company,
            values,
            "error.constraint",
            update=True,
            metrics_id=row.id,
            updated_at=row.updated_at,
        )
    if saved is None:
        return _not_found(request)
    return _see_other(f"/ui/instruments/{company.id}")


@router.get(
    "/companies/{company_id}/metrics/{metrics_id}/delete",
    include_in_schema=False,
)
def delete_metrics_form(
    request: Request,
    company_id: str,
    metrics_id: str,
    db: Session = Depends(get_db),
):
    """Confirmation only. GET does not delete the period."""
    company, row, missing = _load_metrics(request, db, company_id, metrics_id)
    if missing is not None:
        return missing
    return _confirm_page(
        request,
        title_key="page.delete_metrics",
        warning_key="delete.metrics_warning",
        question_key="delete.metrics_question",
        action=f"/ui/companies/{company.id}/metrics/{row.id}/delete",
        cancel_href=f"/ui/instruments/{company.id}",
        company_name=company.name,
        period_end=row.period_end,
        period_type=row.period_type,
    )


@router.post(
    "/companies/{company_id}/metrics/{metrics_id}/delete",
    include_in_schema=False,
)
def delete_metrics(
    request: Request,
    company_id: str,
    metrics_id: str,
    db: Session = Depends(get_db),
):
    """Delete one metrics row. The company stays."""
    company, row, missing = _load_metrics(request, db, company_id, metrics_id)
    if missing is not None:
        return missing
    FinancialMetricsRepository(db).delete(row.id)
    return _see_other(f"/ui/instruments/{company.id}")
