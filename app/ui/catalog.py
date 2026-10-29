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
    "nav.watchlist": "Watchlista",
    "page.watchlist_title": "Watchlista",
    "watchlist.empty": (
        "Watchlista jest pusta. Dodaj spółkę serduszkiem na jej stronie."
    ),
    "watchlist.go_to_instruments": "Przejdź do listy instrumentów",
    "column.company": "Spółka",
    "column.price": "Cena",
    "column.change": "Zmiana",
    "column.trend": "Trend 3 mies.",
    "column.latest_bar": "Notowanie z",
    "watchlist.change_since": "wobec {date}",
    "watchlist.stale": "nieaktualne",
    "watchlist.stale_hint": "Notowanie starsze niż {days} dni",
    "watchlist.no_prices": "brak notowań",
    "watchlist.source": "źródło: {source}",
    "watchlist.add": "Dodaj do watchlisty",
    "watchlist.remove": "Usuń z watchlisty",
    "watchlist.remove_named": "Usuń {name} z watchlisty",
    "research.toggle": "Notatki i tezy",
    "research.toggle_count": "Notatki i tezy ({count})",
    "research.theses": "Tezy",
    "research.notes": "Notatki",
    "research.no_theses": "Brak tez.",
    "research.no_active_theses": "Brak aktywnych tez.",
    "research.no_notes": "Brak notatek.",
    "research.edited": "edytowano {datetime}",
    "research.since": "od {date}",
    "research.closed_on": "zamknięta {date}",
    "research.status_active": "aktywna",
    "research.status_closed": "zamknięta",
    "research.closed_theses": "Zamknięte tezy ({count})",
    "field.thesis_body": "Dlaczego kupiłem",
    "field.thesis_breakers": "Kiedy sprzedam / co złamie tezę",
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
    "field.isin": "ISIN",
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
    "type.etf": "ETF",
    "type.etc": "ETC",
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
    "action.create_company": "Dodaj instrument",
    "action.edit_company": "Edytuj instrument",
    "action.delete_company": "Usuń instrument",
    "action.add_metrics": "Dodaj wskaźniki",
    "action.edit_metrics": "Edytuj wskaźniki",
    "action.delete_metrics": "Usuń wskaźniki",
    "action.save": "Zapisz",
    "action.confirm_delete": "Usuń",
    "action.cancel": "Anuluj",
    "page.create_company": "Nowy instrument",
    "page.edit_company": "Edycja instrumentu",
    "page.delete_company": "Usuwanie instrumentu",
    "page.create_metrics": "Nowe wskaźniki",
    "page.edit_metrics": "Edycja wskaźników",
    "page.delete_metrics": "Usuwanie wskaźników",
    "form.error_summary": "Popraw zaznaczone pola.",
    "field.period_end": "Koniec okresu",
    "field.period_type": "Typ okresu",
    "field.updated_at": "Ostatnia zmiana",
    "delete.company_warning": (
        "Usunięcie tej spółki usuwa także jej wskaźniki finansowe."
    ),
    "delete.company_question": "Usunąć tę spółkę?",
    "delete.metrics_warning": ("Usunięcie tych wskaźników nie usuwa spółki."),
    "delete.metrics_question": "Usunąć te wskaźniki?",
    "hint.period_end": (
        "Czas bez strefy jest zapisywany jako UTC. "
        "Przykład: 2024-12-31T00:00:00."
    ),
    "hint.period_type": (
        "Do 20 znaków. Strona szczegółów grupuje annual i quarterly. "
        "Inna wartość trafia do innych okresów."
    ),
    "hint.period_type_locked": (
        "Typ okresu zostaje taki, jak przy utworzeniu wskaźników."
    ),
    "hint.numbers": (
        "Puste pole oznacza brak danych. "
        "NaN i nieskończoność nie są liczbami."
    ),
    "error.required": "To pole jest wymagane.",
    "error.too_long": "Za długa wartość.",
    "error.too_short": "Za krótka wartość.",
    "error.ticker": (
        "Ticker musi mieć od 1 do 20 znaków ASCII: "
        "litery, cyfry albo . _ - ^ =."
    ),
    "error.currency": "Waluta musi mieć dokładnie trzy litery.",
    "error.website": (
        "Podaj adres http:// lub https:// albo zostaw pole puste."
    ),
    "error.number": "Podaj skończoną liczbę albo zostaw pole puste.",
    "error.datetime": ("Podaj datę i czas, na przykład 2024-12-31T00:00:00."),
    "error.invalid": "Ta wartość jest nieprawidłowa.",
    "error.instrument_type": "Typ musi być STOCK, ETF albo ETC.",
    "error.duplicate_company": (
        "Istnieje już spółka o tej nazwie lub tym tickerze."
    ),
    "error.duplicate_ticker": "Istnieje już spółka o tym tickerze.",
    "error.duplicate_isin": "Istnieje już spółka o tym numerze ISIN.",
    "error.duplicate_metrics": (
        "Wskaźniki dla tej spółki, końca okresu i typu okresu już istnieją."
    ),
    "error.constraint": (
        "Nie można zapisać tych danych, bo naruszają regułę unikalności."
    ),
    "error.method_title": "Metoda niedozwolona",
    "error.method_body": "Ta strona nie obsługuje tej metody.",
    "error.forbidden_title": "Żądanie zostało odrzucone",
    "error.forbidden_body": (
        "Zmiana danych jest możliwa tylko z tej samej strony."
    ),
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
    "nav.watchlist": "Watchlist",
    "page.watchlist_title": "Watchlist",
    "watchlist.empty": (
        "Your watchlist is empty. Add a company with the heart on its page."
    ),
    "watchlist.go_to_instruments": "Go to the instrument list",
    "column.company": "Company",
    "column.price": "Price",
    "column.change": "Change",
    "column.trend": "3-month trend",
    "column.latest_bar": "Price date",
    "watchlist.change_since": "vs {date}",
    "watchlist.stale": "stale",
    "watchlist.stale_hint": "Price older than {days} days",
    "watchlist.no_prices": "no prices",
    "watchlist.source": "source: {source}",
    "watchlist.add": "Add to watchlist",
    "watchlist.remove": "Remove from watchlist",
    "watchlist.remove_named": "Remove {name} from watchlist",
    "research.toggle": "Notes and theses",
    "research.toggle_count": "Notes and theses ({count})",
    "research.theses": "Theses",
    "research.notes": "Notes",
    "research.no_theses": "No theses yet.",
    "research.no_active_theses": "No active theses.",
    "research.no_notes": "No notes yet.",
    "research.edited": "edited {datetime}",
    "research.since": "since {date}",
    "research.closed_on": "closed {date}",
    "research.status_active": "active",
    "research.status_closed": "closed",
    "research.closed_theses": "Closed theses ({count})",
    "field.thesis_body": "Why I bought",
    "field.thesis_breakers": "When I sell / what breaks the thesis",
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
    "field.isin": "ISIN",
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
    "type.etf": "ETF",
    "type.etc": "ETC",
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
    "action.create_company": "Add instrument",
    "action.edit_company": "Edit instrument",
    "action.delete_company": "Delete instrument",
    "action.add_metrics": "Add metrics",
    "action.edit_metrics": "Edit metrics",
    "action.delete_metrics": "Delete metrics",
    "action.save": "Save",
    "action.confirm_delete": "Delete",
    "action.cancel": "Cancel",
    "page.create_company": "New instrument",
    "page.edit_company": "Edit instrument",
    "page.delete_company": "Delete instrument",
    "page.create_metrics": "New metrics",
    "page.edit_metrics": "Edit metrics",
    "page.delete_metrics": "Delete metrics",
    "form.error_summary": "Correct the highlighted fields.",
    "field.period_end": "Period end",
    "field.period_type": "Period type",
    "field.updated_at": "Last edit",
    "delete.company_warning": (
        "Deleting this company also deletes its financial metrics."
    ),
    "delete.company_question": "Delete this company?",
    "delete.metrics_warning": (
        "Deleting these metrics does not delete the company."
    ),
    "delete.metrics_question": "Delete these metrics?",
    "hint.period_end": (
        "A time with no zone is stored as UTC. "
        "Example: 2024-12-31T00:00:00."
    ),
    "hint.period_type": (
        "Up to 20 characters. The detail page groups annual and "
        "quarterly. Any other value is listed under other periods."
    ),
    "hint.period_type_locked": (
        "The period type stays as it was when these metrics were created."
    ),
    "hint.numbers": (
        "Leave a field empty when the number is missing. "
        "NaN and infinity are not numbers."
    ),
    "error.required": "This field is required.",
    "error.too_long": "This value is too long.",
    "error.too_short": "This value is too short.",
    "error.ticker": (
        "Ticker must be 1 to 20 ASCII characters: "
        "letters, digits, or . _ - ^ =."
    ),
    "error.currency": "Currency must be exactly three letters.",
    "error.website": (
        "Enter an http:// or https:// address, or leave the field empty."
    ),
    "error.number": "Enter a finite number, or leave the field empty.",
    "error.datetime": ("Enter a date and time, such as 2024-12-31T00:00:00."),
    "error.invalid": "This value is not valid.",
    "error.instrument_type": "Type must be STOCK, ETF, or ETC.",
    "error.duplicate_company": (
        "A company with this name or ticker already exists."
    ),
    "error.duplicate_ticker": "A company with this ticker already exists.",
    "error.duplicate_isin": "A company with this ISIN already exists.",
    "error.duplicate_metrics": (
        "Metrics for this company, period end, and period type "
        "already exist."
    ),
    "error.constraint": (
        "These values cannot be saved because they are not unique."
    ),
    "error.method_title": "Method not allowed",
    "error.method_body": "This page does not accept this method.",
    "error.forbidden_title": "Request rejected",
    "error.forbidden_body": "Changes are only accepted from this site.",
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
