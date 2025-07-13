# Investment AI Companion

Application for stock market analysis using artificial intelligence to collect and analyze data from various sources.

## Features

- Collecting data about companies from American, Polish and European stock exchanges
- Integration with ChatGPT for data analysis
- Web scraping of news and social media
- Sentiment analysis and report generation
- Dashboard for data presentation

## Project Structure

```
investment_ai_companion/
├── app/
│   ├── api/                 # API endpoints
│   ├── core/               # Configuration and constants
│   ├── data_collectors/    # Data collection modules
│   ├── ai/                 # AI integration and analysis
│   ├── models/             # Data models
│   └── services/           # Business logic
├── tests/                  # Tests
├── scripts/                # Helper scripts
├── config/                 # Configuration files
└── docs/                   # Documentation
```

## Requirements

- Python 3.9+
- PostgreSQL
- Redis
- Elasticsearch (optional)

## Installation

1. Clone the repository:
```bash
git clone [repository_url]
cd investment_ai_companion
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env file and set appropriate values
```

5. Run the application:
```bash
python main.py
```

## Configuration

The application requires configuring the following environment variables:
- `OPENAI_API_KEY` - API key for ChatGPT
- `DATABASE_URL` - PostgreSQL database URL
- `REDIS_URL` - Redis URL
- `ELASTICSEARCH_URL` - Elasticsearch URL (optional)

## License

MIT
