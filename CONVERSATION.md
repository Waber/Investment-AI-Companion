# Investment AI Companion - Historia Rozwoju

## Sesja 1: Inicjalizacja Projektu
- Data: [Data rozpoczęcia]
- Status: ✅ Zakończona

### Podjęte Decyzje
1. Wybór technologii:
   - Język: Python
   - Framework webowy: FastAPI
   - Baza danych: PostgreSQL
   - Cache: Redis
   - Wyszukiwarka: Elasticsearch

2. Struktura projektu:
   ```
   InvestmentAiCompanion/
   ├── app/
   │   ├── api/          # Endpointy API
   │   ├── core/         # Konfiguracja, stałe
   │   ├── models/       # Modele danych
   │   ├── services/     # Logika biznesowa
   │   ├── ai/           # Integracja z AI
   │   └── data_collectors/  # Web scraping, API
   ├── tests/            # Testy
   ├── docs/             # Dokumentacja
   ├── scripts/          # Skrypty pomocnicze
   └── config/           # Pliki konfiguracyjne
   ```

3. Zainicjalizowane pliki:
   - `requirements.txt` - zależności projektu
   - `README.md` - dokumentacja projektu
   - `main.py` - główny plik aplikacji
   - `.gitignore` - ignorowane pliki
   - `.env` - zmienne środowiskowe

### Zaimplementowane Funkcjonalności
1. Podstawowa konfiguracja FastAPI
2. System konfiguracji z użyciem pydantic-settings
3. Modele danych:
   - `Company` - podstawowe informacje o firmie
   - `FinancialMetrics` - wskaźniki finansowe
   - `HistoricalData` - dane historyczne

### Następne Kroki
1. Implementacja endpointów API
2. Integracja z bazą danych
3. Implementacja serwisów do zbierania danych
4. Integracja z AI

## Sesja 2: Modele Danych
- Data: [Data sesji]
- Status: ✅ Zakończona

### Zaimplementowane Modele
1. `Company` (app/models/company.py):
   - Podstawowe dane firmy (nazwa, ticker, sektor)
   - Informacje o notowaniu (giełda, waluta)
   - Metadane (daty utworzenia/aktualizacji)

2. `FinancialMetrics` (app/models/financial_metrics.py):
   - Wskaźniki rentowności (ROE, ROA, marże)
   - Wskaźniki płynności
   - Wskaźniki zadłużenia
   - Wskaźniki efektywności
   - Wskaźniki wzrostu
   - Wskaźniki wyceny
   - Dodatkowe wskaźniki

3. `HistoricalData` (app/models/historical_data.py):
   - Dane OHLCV
   - Dodatkowe dane rynkowe
   - Wskaźniki techniczne

### Następne Kroki
1. Implementacja endpointów API do zarządzania firmami
2. Integracja z Yahoo Finance do pobierania danych
3. Implementacja web scrapingu
4. Integracja z OpenAI do analizy danych

## Sesja 3: Refaktoryzacja endpointów
- Data: [Data sesji]
- Status: ✅ Zakończona

### Zmiany
1. Refaktoryzacja endpointu POST /companies:
   - Zamiast ręcznego mapowania pól, użyto rozpakowywania słownika z `company.model_dump()` (Pydantic v2) przy tworzeniu obiektu `Company`.
   - Przy aktualizacji używamy `c.model_copy(update=company.model_dump(exclude_unset=True))`, co aktualizuje tylko pola faktycznie przesłane w żądaniu (partial update) i zachowuje resztę bez zmian. Dodatkowo aktualizujemy `updated_at`.
   - Dzięki temu kod jest bardziej czytelny i mniej podatny na błędy przy zmianach modelu wejściowego.

### Następne Kroki
1. Podpięcie bazy danych (SQLAlchemy) i zastąpienie pamięci w RAM (list) trwałym magazynem danych.
2. Walidacje i ograniczenia unikalności na poziomie bazy (np. unikalny `ticker` dla `Company`, unikalność `(company_id, period_end, period_type)` dla `FinancialMetrics`).
3. Przygotowanie migracji (Alembic) i skryptów inicjalizacyjnych.
4. Testy jednostkowe i integracyjne (pytest + httpx) dla endpointów.
5. Dokumentacja: opis endpointów i przykładowe żądania/odpowiedzi.

## Sesja 4: Integracja SQLAlchemy
- Data: [Data sesji]
- Status: ✅ Zakończona

### Zaimplementowane Funkcjonalności

#### 1. Warstwa bazy danych (app/core/database.py)
- **SQLAlchemy Engine**: Konfiguracja połączenia z bazą PostgreSQL
- **SessionLocal**: Fabryka sesji bazodanowych dla każdego żądania
- **Base**: Klasa bazowa dla wszystkich modeli SQLAlchemy
- **get_db()**: Dependency injection dla FastAPI - automatyczne zarządzanie sesjami

#### 2. Modele SQLAlchemy (app/models/database_models.py)
- **CompanyDB**: Tabela `companies` z indeksami i ograniczeniami unikalności
- **FinancialMetricsDB**: Tabela `financial_metrics` z relacją do companies
- **Relacje**: One-to-many między Company a FinancialMetrics
- **Ograniczenia**: Unikalne tickery, kompozytowe klucze unikalne

#### 3. Warstwa repozytoriów
- **CompanyRepository**: Operacje CRUD dla firm z obsługą błędów
- **FinancialMetricsRepository**: Operacje CRUD dla wskaźników finansowych
- **Walidacja**: Sprawdzanie unikalności przed zapisem
- **Transakcje**: Automatyczne commit/rollback

#### 4. Aktualizacja API
- **Dependency Injection**: Automatyczne wstrzykiwanie sesji bazodanowych
- **Konwersja modeli**: Helper functions do konwersji SQLAlchemy ↔ Pydantic
- **Obsługa błędów**: HTTP status codes dla różnych typów błędów
- **Paginacja**: Wsparcie dla `skip` i `limit` w endpointach list

#### 5. Migracje i inicjalizacja
- **Alembic**: Konfiguracja do zarządzania schematem bazy
- **Startup Event**: Automatyczne tworzenie tabel przy uruchomieniu aplikacji
- **Seed Data**: Skrypt do dodawania przykładowych danych

### Kluczowe Korzyści Architektury
1. **Separacja odpowiedzialności**: API ↔ Repository ↔ Database
2. **Testowanie**: Możliwość mockowania repozytoriów
3. **Skalowalność**: Łatwe dodawanie nowych operacji bazodanowych
4. **Bezpieczeństwo**: Automatyczne zarządzanie sesjami i transakcjami
5. **Wydajność**: Indeksy bazodanowe i optymalizacje zapytań

### Następne Kroki
1. **Testy**: Implementacja testów jednostkowych i integracyjnych
2. **Dokumentacja API**: Rozszerzenie Swagger/OpenAPI
3. **Logowanie**: Dodanie systemu logowania operacji bazodanowych
4. **Cache**: Integracja Redis dla często używanych danych
5. **Monitoring**: Metryki wydajności zapytań

## Uwagi do Synchronizacji
- Projekt jest w repozytorium Git
- Wszystkie zmienne środowiskowe są w pliku `.env` (ignorowanym przez Git)
- Przy przenoszeniu na nową maszynę:
  1. Sklonować repozytorium
  2. Skopiować plik `.env`
  3. Zainstalować zależności: `pip install -r requirements.txt`
  4. Uruchomić aplikację: `python -m uvicorn main:app --reload`

## Notatki: Pydantic v2 i mapowanie pól

1. `model_dump()` zamiast `dict()` w Pydantic v2:
   - `model_dump()` tworzy zwykły słownik z danych modelu (np. `CompanyCreate`).
   - `model_dump(exclude_unset=True)` zwraca tylko pola faktycznie przesłane przez klienta (przydatne przy aktualizacjach `PUT`).

2. Rozpakowywanie słownika do konstruktora (`**`):
   - W Pythonie `**slownik` rozpakowuje pary klucz-wartość jako argumenty nazwane funkcji/konstruktora.
   - Przykład (schematyczny):
     ```python
     payload = company.model_dump()
     new_company = Company(id=1, created_at=..., updated_at=..., **payload)
     ```

3. Częściowa aktualizacja z `model_copy(update=...)`:
   - `nowy = stary.model_copy(update=zmiany)` tworzy kopię obiektu z nadpisanymi polami.
   - Używamy z `model_dump(exclude_unset=True)`, aby nie usuwać nieprzesłanych pól.

4. Integracja z ORM: `from_attributes = True`:
   - Pozwala Pydanticowi tworzyć model na podstawie obiektu ORM (np. SQLAlchemy) bez ręcznego mapowania.

## Jak uruchomić aplikację (krok po kroku)

1. Aktywuj wirtualne środowisko i zainstaluj zależności:
   - macOS/Linux:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     pip install -r requirements.txt
     ```
   - Windows (PowerShell):
     ```powershell
     python -m venv venv
     .\\venv\\Scripts\\Activate.ps1
     pip install -r requirements.txt
     ```

2. Uruchom serwer deweloperski:
   ```bash
   python -m uvicorn main:app --reload
   ```
   - Interaktywna dokumentacja: `http://127.0.0.1:8000/docs`

## Szybkie testy endpointów (curl)

- Utworzenie firmy:
  ```bash
  curl -X POST http://127.0.0.1:8000/companies/ \
    -H "Content-Type: application/json" \
    -d '{
      "name": "Acme Corp",
      "ticker": "ACME",
      "sector": "Technology",
      "industry": "Software",
      "website": "https://example.com",
      "country": "USA",
      "exchange": "NASDAQ",
      "currency": "USD"
    }'
  ```

- Lista firm:
  ```bash
  curl http://127.0.0.1:8000/companies/
  ```

- Aktualizacja firmy (częściowa):
  ```bash
  curl -X PUT http://127.0.0.1:8000/companies/1 \
    -H "Content-Type: application/json" \
    -d '{"sector": "Information Technology"}'
  ```

- Usunięcie firmy:
  ```bash
  curl -X DELETE http://127.0.0.1:8000/companies/1 -i
  ```

- Utworzenie wskaźników finansowych:
  ```bash
  curl -X POST http://127.0.0.1:8000/financial-metrics/ \
    -H "Content-Type: application/json" \
    -d '{
      "company_id": 1,
      "period_end": "2024-12-31T00:00:00Z",
      "period_type": "annual",
      "revenue": 1000000,
      "net_income": 200000
    }'
  ```

- Wskaźniki danej firmy:
  ```bash
  curl http://127.0.0.1:8000/financial-metrics/company/1
  ```

## Co teraz (najbliższe zadania)

1. Podłączyć SQLAlchemy (modele, sesja, migracje Alembic).
2. Zastąpić listy w RAM operacjami na bazie (repozytoria/serwisy).
3. Dodać ograniczenia unikalności na poziomie bazy i odpowiednie obsługi błędów (HTTP 400/409).
4. Dodać testy (pytest + httpx) i zacząć pokrywać krytyczne ścieżki.
5. Uzupełnić dokumentację przypadków brzegowych i przykładów żądań.