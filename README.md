# Investment AI Companion

Aplikacja do analizy spółek giełdowych wykorzystująca sztuczną inteligencję do zbierania i analizy danych z różnych źródeł.

## Funkcjonalności

- Zbieranie danych o spółkach z giełd amerykańskich, polskich i europejskich
- Integracja z ChatGPT do analizy danych
- Web scraping newsów i social media
- Analiza sentymentu i generowanie raportów
- Dashboard do prezentacji danych

## Struktura projektu

```
investment_ai_companion/
├── app/
│   ├── api/                 # Endpointy API
│   ├── core/               # Konfiguracja i stałe
│   ├── data_collectors/    # Moduły zbierania danych
│   ├── ai/                 # Integracja z AI i analiza
│   ├── models/             # Modele danych
│   └── services/           # Logika biznesowa
├── tests/                  # Testy
├── scripts/                # Skrypty pomocnicze
├── config/                 # Pliki konfiguracyjne
└── docs/                   # Dokumentacja
```

## Wymagania

- Python 3.9+
- PostgreSQL
- Redis
- Elasticsearch (opcjonalnie)

## Instalacja

1. Sklonuj repozytorium:
```bash
git clone [url_repozytorium]
cd investment_ai_companion
```

2. Utwórz i aktywuj środowisko wirtualne:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# lub
.\venv\Scripts\activate  # Windows
```

3. Zainstaluj zależności:
```bash
pip install -r requirements.txt
```

4. Skonfiguruj zmienne środowiskowe:
```bash
cp .env.example .env
# Edytuj plik .env i ustaw odpowiednie wartości
```

5. Uruchom aplikację:
```bash
python main.py
```

## Konfiguracja

Aplikacja wymaga skonfigurowania następujących zmiennych środowiskowych:
- `OPENAI_API_KEY` - klucz API do ChatGPT
- `DATABASE_URL` - URL do bazy danych PostgreSQL
- `REDIS_URL` - URL do Redis
- `ELASTICSEARCH_URL` - URL do Elasticsearch (opcjonalnie)

## Licencja

MIT
