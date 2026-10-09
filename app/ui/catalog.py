"""Polish and English message catalogs for the /ui pages.

Simple dicts, not gettext. The UI has two languages and a few dozen
strings, so a catalog a reader can open in one file is enough. Add a
string by putting the same key in both dicts. ``translate`` falls back
to Polish when the selected language has no entry. A test checks that
the two catalogs have the same keys, so a missing translation fails
before a page renders the key name.

Data values (names, tickers, source ids) are not in these catalogs.
"""

LANGUAGE_COOKIE = "ui_lang"
SUPPORTED_LANGUAGES = ("pl", "en")
DEFAULT_LANGUAGE = "pl"

_POLISH = {
    "app_name": "Investment AI Companion",
    "disclaimer": (
        "To narzędzie pomaga w analizie i porządkowaniu decyzji. "
        "Nie jest poradą inwestycyjną. "
        "Nie wskazuje, co kupić ani sprzedać."
    ),
    "language.label": "Język",
    "language.pl": "PL",
    "language.en": "EN",
    "nav.instruments": "Instrumenty",
    "page.list_title": "Instrumenty",
    "page.detail_title": "Szczegóły instrumentu",
    "filter.search": "Szukaj",
    "filter.type": "Typ",
    "filter.exchange": "Giełda",
    "filter.currency": "Waluta",
    "filter.any": "wszystkie",
    "filter.apply": "Filtruj",
    "nav.skip": "Przejdź do treści",
    "column.ticker": "Ticker",
    "column.name": "Nazwa",
    "column.type": "Typ",
    "column.exchange": "Giełda",
    "column.currency": "Waluta",
    "column.source": "Źródło",
    "column.as_of": "Stan na",
    "column.metric": "Wskaźnik",
    "badge.synthetic": "dane syntetyczne",
    "missing": "brak danych",
    "list.empty": "Brak instrumentów",
    "field.ticker": "Ticker",
    "field.name": "Nazwa",
    "field.type": "Typ",
    "field.exchange": "Giełda",
    "field.currency": "Waluta",
    "field.country": "Kraj",
    "field.sector": "Sektor",
    "field.industry": "Branża",
    "field.website": "Strona",
    "field.description": "Opis",
    "field.source": "Źródło",
    "field.as_of": "Stan na",
    "type.stock": "akcja",
    "metrics.annual": "Dane roczne",
    "metrics.quarterly": "Dane kwartalne",
    "metrics.other": "Inne okresy",
    "metrics.none": "Brak raportów",
    "not_found.title": "Nie znaleziono instrumentu",
    "not_found.body": (
        "Ten identyfikator nie wskazuje zapisanego instrumentu."
    ),
    "metric.revenue": "Przychody",
    "metric.net_income": "Zysk netto",
    "metric.total_assets": "Aktywa razem",
    "metric.total_liabilities": "Zobowiązania razem",
    "metric.total_equity": "Kapitał własny",
    "metric.roe": "ROE",
    "metric.roa": "ROA",
    "metric.gross_margin": "Marża brutto",
    "metric.net_margin": "Marża netto",
    "metric.current_ratio": "Wskaźnik bieżący",
    "metric.quick_ratio": "Wskaźnik szybki",
    "metric.debt_to_equity": "Dług do kapitału",
    "metric.debt_to_assets": "Dług do aktywów",
    "metric.asset_turnover": "Rotacja aktywów",
    "metric.inventory_turnover": "Rotacja zapasów",
    "metric.revenue_growth": "Wzrost przychodów",
    "metric.net_income_growth": "Wzrost zysku netto",
    "metric.pe_ratio": "Cena/zysk (P/E)",
    "metric.pb_ratio": "Cena/wartość księgowa (P/B)",
    "metric.ev_ebitda": "EV/EBITDA",
}

_ENGLISH = {
    "app_name": "Investment AI Companion",
    "disclaimer": (
        "This tool helps with research and decision hygiene. "
        "It is not financial advice. "
        "It does not say what to buy or sell."
    ),
    "language.label": "Language",
    "language.pl": "PL",
    "language.en": "EN",
    "nav.instruments": "Instruments",
    "page.list_title": "Instruments",
    "page.detail_title": "Instrument details",
    "filter.search": "Search",
    "filter.type": "Type",
    "filter.exchange": "Exchange",
    "filter.currency": "Currency",
    "filter.any": "any",
    "filter.apply": "Apply",
    "nav.skip": "Skip to main content",
    "column.ticker": "Ticker",
    "column.name": "Name",
    "column.type": "Type",
    "column.exchange": "Exchange",
    "column.currency": "Currency",
    "column.source": "Source",
    "column.as_of": "As of",
    "column.metric": "Metric",
    "badge.synthetic": "synthetic data",
    "missing": "no data",
    "list.empty": "No instruments",
    "field.ticker": "Ticker",
    "field.name": "Name",
    "field.type": "Type",
    "field.exchange": "Exchange",
    "field.currency": "Currency",
    "field.country": "Country",
    "field.sector": "Sector",
    "field.industry": "Industry",
    "field.website": "Website",
    "field.description": "Description",
    "field.source": "Source",
    "field.as_of": "As of",
    "type.stock": "stock",
    "metrics.annual": "Annual figures",
    "metrics.quarterly": "Quarterly figures",
    "metrics.other": "Other periods",
    "metrics.none": "No reports",
    "not_found.title": "Instrument not found",
    "not_found.body": "This identifier does not match a stored instrument.",
    "metric.revenue": "Revenue",
    "metric.net_income": "Net income",
    "metric.total_assets": "Total assets",
    "metric.total_liabilities": "Total liabilities",
    "metric.total_equity": "Total equity",
    "metric.roe": "ROE",
    "metric.roa": "ROA",
    "metric.gross_margin": "Gross margin",
    "metric.net_margin": "Net margin",
    "metric.current_ratio": "Current ratio",
    "metric.quick_ratio": "Quick ratio",
    "metric.debt_to_equity": "Debt to equity",
    "metric.debt_to_assets": "Debt to assets",
    "metric.asset_turnover": "Asset turnover",
    "metric.inventory_turnover": "Inventory turnover",
    "metric.revenue_growth": "Revenue growth",
    "metric.net_income_growth": "Net income growth",
    "metric.pe_ratio": "Price to earnings (P/E)",
    "metric.pb_ratio": "Price to book (P/B)",
    "metric.ev_ebitda": "EV/EBITDA",
}

CATALOGS = {"pl": _POLISH, "en": _ENGLISH}


def translate(language, key, catalogs=None):
    """Return ``key`` in ``language``, falling back to Polish.

    An unknown language uses the Polish catalog. A key that English
    does not have uses the Polish text. A key that Polish does not
    have either is returned as the key, so a typo is visible and the
    page still renders.
    """
    selected_catalogs = CATALOGS if catalogs is None else catalogs
    if language not in selected_catalogs:
        language = DEFAULT_LANGUAGE
    selected = selected_catalogs.get(language, {})
    if key in selected:
        return selected[key]
    polish = selected_catalogs.get(DEFAULT_LANGUAGE, {})
    if key in polish:
        return polish[key]
    return key
