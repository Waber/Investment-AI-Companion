# Investment AI Companion: Product Requirements (Draft)

- Status: draft v0.3, 2026-10-08. Prepared from the repository state at master `d568663` and Raul's decisions of 2026-10-08 (three rounds). v0.2 added: UI and database confirmed, PL/EN language switch, scoring in scope, yfinance as the primary data source, Gemini as the AI provider after the demo. **v0.3 adds the post-demo direction (section 12):** server deployment for the owner only, login, private portfolio holdings, and a scheduled market scanner with buy/sell/opportunity signals and notifications. "No authentication/hosting" and "the score is never a buy/sell signal" now apply to the **demo phase only**; the demo itself is unchanged (local, loopback, no auth, no signals). Section 4 criteria US3.1 and US6 keep the disclaimer in both phases.
- Owner: Raul (product decisions). Prepared by the Project Manager agent for the Developer, QA Engineer and Code Reviewer.
- Related docs: `AGENTS.md`, `docs/superpowers/specs/2026-09-08-research-workflow-and-hardening-design.md`, `docs/demo-data.md`, `docs/work-state.md`.
- Research inputs (Researcher, 2026-10-08; land in the repo via PR under `docs/research/`): `docs/research/market-data-sources.md` (market-data sources), `docs/research/llm-comparison.md` (LLM providers), and `docs/research/hosting-options.md` (hosting options; research input, not a decision).
- Items marked **[Decided]** were confirmed by Raul. Items marked **[Proposal]** still need his confirmation. Items marked **[Open]** are undecided.

## 1. Purpose and vision

Investment AI Companion is Raul's personal investment research tool. In the demo phase it runs locally; after the demo it is meant to run on a server for Raul alone (section 12). It helps him:
- understand and compare listed stocks, ETFs and ETCs;
- see a transparent, explainable score per instrument;
- track a watchlist;
- record his own notes and investment theses;
- get structured AI analyses that cite their sources.

It is also a project for learning Python, so code and docs must stay readable for a developer who is still learning (see `AGENTS.md`).

The tool supports research and decision hygiene. In both phases it never gives financial advice. **In the demo phase** it never gives buy/sell instructions. After the demo, Raul wants personal buy/sell/"interesting company" signals (section 12); they are **personal decision support, not financial advice**. In both phases, **transparency is a principle**: every analysis, score and signal shows its sources, how fresh the data is, its assumptions, its risks and its uncertainty.

## 2. User and context

- **Primary user:** Raul. The tool runs locally on his machine. Other people may look at the app on his machine (hence the English option), but in the demo there are no accounts, roles or remote users.
- **No authentication, no hosting (demo phase only).** In the demo phase the HTTP server binds to `127.0.0.1` only, and a public or tunnelled exposure must stay off. After the demo the app runs on a server for the owner only, behind login and HTTPS (section 12; #48, #56).
- **Language [Decided]:** the UI has a **PL/EN language switch, Polish by default**. AI analyses are generated in Polish by default and follow the selected UI language when EN is chosen. Code, identifiers and technical documentation stay in English, as the repo convention requires.
- **Technical context:** the existing FastAPI, SQLAlchemy and Pydantic backend; Python 3.12; the SQLite test suite with CI on GitHub Actions.
- **Databases [Decided]:** **PostgreSQL is the personal database** (notes, theses, watchlist, real data). **SQLite is used for tests and the disposable demo only.**

## 3. Scope

**In scope**
1. An overview of each instrument (stock, ETF, ETC) with its metrics, comparisons between instruments, and trends over time.
2. A watchlist of tracked instruments.
3. AI analysis of a selected instrument: cited sources, base/upside/downside scenarios, risks, assumptions, freshness, and the not-financial-advice guardrails.
4. Real market data via **yfinance** (primary) behind a collector interface, plus an offline fake for demo and tests.
5. Personal notes and investment theses attached to instruments.
6. A server-rendered web UI **[Decided]**: Jinja2 + HTMX inside FastAPI under `/ui`, pure Python, with a PL/EN switch.
7. **A transparent, explainable score per instrument [Decided]** (US6): visible components, weights and data freshness; configurable weights; in the demo phase never labelled as a buy/sell signal (post-demo signals are a separate feature built on the score, section 12).
8. An offline demo mode with synthetic data and mocked AI.

**Out of scope**
- Bonds, derivatives (futures, options, CFDs), crypto, mutual funds outside ETFs.
- Trading, order execution and broker API integration.
- Holdings and allocations, portfolio performance tracking: **demo phase only**; post-demo portfolio holdings are planned (section 12, #57).
- Buy/sell/hold signals, recommendations, target prices or "best pick" rankings: **demo phase only**; post-demo scanner signals are planned (section 12, #58).
- Multiple users and mobile apps. Authentication and hosting: **demo phase only** (section 12, #48, #56).
- Paid AI calls in the demo or in automated tests.
- Redis, Elasticsearch, news and social-media scraping. These are listed as "planned" in `.env.example` and `CONVERSATION.md` but are not part of this product scope. Schedulers: demo phase only (the post-demo market scanner needs one, section 12).

**Deferred or optional**
- **Investor profiles** (issue #12, plan Task 4). Deferred: not a core use case. Bring them back only if they turn out to be needed to tailor AI analysis.
- **Paid data fallback (EODHD)**: documented, not implemented (section 7).

## 4. User stories and acceptance criteria

### US1. Instrument overview, comparison and trends
- **US1.1** As Raul, I want to browse and search instruments by type, exchange, country and currency, so that I can find what to research.
  - [ ] The list filters by type (stock, ETF, ETC), exchange and currency, and searches by name, ticker or ISIN.
  - [ ] Each row shows the type, exchange, currency, data source and the "as of" date of the latest data.
- **US1.2** As Raul, I want an instrument detail page, so that I can see its descriptive data and the metrics that apply to its type.
  - [ ] Stocks show financial statement metrics, with annual and quarterly periods in separate tables.
  - [ ] ETFs and ETCs show fund attributes and price-based metrics (see section 5).
  - [ ] Missing values are shown as "brak danych" / "no data" (per language), never as 0. Monetary values always show their currency.
- **US1.3** As Raul, I want a chart of a metric or price over time, so that I can see trends.
  - [ ] I can choose the metric and the time range. Annual and quarterly series are never mixed on one axis.
  - [ ] The chart shows the source and the "as of" date.
- **US1.4** As Raul, I want to compare 2–5 instruments side by side.
  - [ ] Only comparable metrics are shown, meaning metrics that exist for every selected type.
  - [ ] A visible warning appears when currencies, period types or "as of" dates differ.
  - [ ] There is no FX conversion unless one is decided later (see section 10).
- **US1.5** As Raul or a visitor, I want to switch the UI between Polish and English.
  - [ ] Polish is the default on first visit. The switch is visible on every page, and the choice persists across pages and restarts (e.g. a cookie; no account needed).
  - [ ] All UI text, labels, the disclaimer, badges and error messages exist in both languages; a missing translation falls back to Polish and is caught by a test.
  - [ ] Number and date formatting follows the selected language. APIs keep ISO and machine formats.
  - [ ] Data values (instrument names, source excerpts) are not translated.

### US2. Watchlist
- **US2.1** As Raul, I want to add instruments to my watchlist and remove them, so that I can track a short list.
  - [ ] I can add or remove from the list page and from the detail page. Adding is idempotent, so the same instrument is never added twice.
  - [ ] The watchlist page shows the latest price or metric, its "as of" date, and a stale-data marker (threshold **[Proposal]**: more than 7 days for prices).
  - [ ] The watchlist persists across restarts and survives an instrument data refresh.
- **US2.2** **[Proposal]** One watchlist in v1. Named lists are deferred.

### US3. AI analysis
- **US3.1** As Raul, I want to request an analysis of a selected instrument, so that I get a structured, cited overview in my selected language (Polish by default).
  - [ ] The output follows the schema in section 6: summary, cited observations, risks, base/upside/downside scenarios, assumptions, thesis-breakers, open questions and uncertainty.
  - [ ] The analysis language equals the UI language at request time and is stored with the analysis.
  - [ ] Every factual observation cites at least one known evidence ID. An analysis with unknown citations is rejected and is not saved.
  - [ ] Freshness warnings appear for evidence older than 180 days (the existing spec) or dated in the future.
  - [ ] The disclaimer is always visible (both phases). In the demo there is no imperative buy/sell language.
- **US3.2** As Raul, I want to see past analyses for an instrument, so that I can compare them over time.
  - [ ] Each saved analysis keeps an immutable snapshot of its inputs, plus the provider, model, prompt version, language and creation time.
- **US3.3** In demo mode and in tests, the analysis comes from a deterministic mock (PL and EN). It is labelled clearly as a demo analysis and makes no network calls.

### US4. Real market data
- **US4.1** As Raul, I want to import or refresh real data for an instrument from yfinance, so that I can research actual instruments.
  - [ ] Each stored value records its source, the "as of" date and the time it was retrieved.
  - [ ] Synthetic records are visibly marked and never mixed silently with real data.
  - [ ] A provider error, rate limit or missing data is shown to the user and never stored as zero.
  - [ ] The instrument type (STOCK/ETF/ETC) comes from the app's own data keyed by ISIN, not from Yahoo's `quoteType` (Yahoo reports ETCs as `EQUITY`).
- **US4.2** Demo mode and tests use only the offline fake collector.

### US5. Notes and investment theses
- **US5.1** As Raul, I want to attach free-text notes to an instrument, so that I can keep my research in one place.
  - [ ] Create, edit and delete notes, ordered by date, with Markdown or plain text **[Proposal]**.
- **US5.2** As Raul, I want to record an investment thesis with its expected drivers and thesis-breakers, and mark it active or closed.
  - [ ] Each thesis has a title, a body, thesis-breakers, a status (active or closed), and creation and update dates.
- **US5.3** Notes and theses stay local.
  - [ ] They are included in an AI analysis only when I tick an explicit option on that request. When included, they are marked as user opinion, not evidence.

### US6. Transparent instrument score [Decided: in scope]
- **US6.1** As Raul, I want each instrument to have a score that I can fully explain, so that I can see at a glance how it looks on the criteria I care about, without being told what to buy.
  - [ ] The score is computed deterministically in code from stored data (never by the LLM), on a fixed scale **[Proposal: 0–100]**.
  - [ ] The detail page shows every component: its name, raw input value(s), normalized component score, weight, contribution to the total, data source and "as of" date.
  - [ ] Components use criteria that fit the instrument type (stock vs ETF/ETC); the default component set per type is **[Open]** (section 10, Q4).
  - [ ] Missing or stale inputs are visible: a missing component is shown as "brak danych" / "no data" and excluded, the remaining weights are renormalized **[Proposal]**, and the score shows a coverage indicator (e.g. "4 of 6 components") and the oldest input date.
  - [ ] Weights are configurable (a settings page or config file **[Proposal]**). Changing weights recomputes scores and the page shows which weight set and score version were used.
  - [ ] **Demo phase:** the score is never labelled or styled as a buy/sell/hold signal or recommendation (no "kupuj"/"buy", no traffic-light advice). **Both phases:** the disclaimer is shown next to the score in both languages. Post-demo signals (section 12) stay a separate view and do not change the demo rule.
  - [ ] The score appears on the detail page and in the comparison view; scores of different instrument types are not presented as directly comparable.
  - [ ] Unit tests pin the formula for fixture inputs, including missing data and custom weights.

## 5. Data model implications

The model generalizes from `companies` to `instruments`. Today's `companies` and `financial_metrics` tables and the fixture only model companies (`docs/demo-data.md`). **[Proposal]** entities:

| Entity | Key fields |
|---|---|
| `Instrument` | `id`, `type` (app-owned enum `stock`, `etf`, `etc`), `name`, `ticker`, `exchange` (MIC or code, e.g. XWAR, XNAS, XETR), `country`, `currency`, `isin` (nullable, unique when present; the key for the app's own type mapping), `is_synthetic`, `source`, timestamps. Unique key (`ticker`, `exchange`) instead of a ticker that's unique on its own. |
| Stock details | Today's company fields: sector, industry, description, website. |
| ETF/ETC details | Issuer, tracked index or underlying (ETC: commodity or asset), TER, domicile, replication method, distribution policy, AUM with "as of" date. The exact set is **[Open]** (Q5). |
| `FinancialMetrics` | Stocks only, the existing 20 fields, linked to the instrument. |
| `PriceBar` | Daily OHLCV per instrument, with source and "as of". Needed for ETF/ETC trends, comparisons and price-based score components. Today's `app/models/historical_data.py` is a Pydantic model only and isn't stored. |
| `WatchlistItem` | Instrument, added date, optional short label. |
| `Note`, `Thesis` | Instrument, text fields, status (theses only), timestamps. |
| `ScoreWeights` / `InstrumentScore` | Weight set per instrument type (version, weights per component); computed score with per-component breakdown, inputs' "as of" dates, weight-set version and computed time. Persisting computed scores vs computing on request is **[Proposal: compute on request in v1]**. |
| `Analysis` | Instrument, language, input snapshot, report content, provider and model metadata, prompt version, created date. No profile link. |
| UI language | Stored client-side (cookie) in v1; no user table. |
| `Portfolio`, `Holding` (post-demo) | Owner, portfolio name, base currency; holding = instrument, quantity, cost and currency, dates (or derived from transactions). **Not built in the demo** (section 12, #57). |
| `Signal` (post-demo) | Instrument, type (buy candidate / sell or review / interesting company), triggering rules, inputs with sources and as-of dates, score version, rationale, risks, status. **Not built in the demo** (section 12, #58). |

Other model points:
- **Design constraint for the demo phase [Proposal]:** models must allow a future `owner_id`/`user_id` and a portfolio table to be added **without a rewrite**. Instruments, prices and metrics stay global reference data; user-owned data (watchlist, notes, theses, analyses, score weights, later portfolios and signals) must be able to gain an `owner_id` column via a migration, so keys and unique constraints must not assume a single user forever (e.g. watchlist uniqueness can become `(owner_id, instrument_id)`). **No auth code, user table or owner column in the demo.**
- **Fixture:** a new `demo-v2.json` adds synthetic ETFs and ETCs, price history, and enough data for every score component (including one deliberately incomplete instrument). The v1 companies are kept or migrated.
- **Migrations [Decided]:** PostgreSQL is the personal database, so #8–#10 stay on the main path, right after the demo. The first Alembic migration (#8) captures the **new instrument schema** (instruments, prices, watchlist, notes/theses, analyses, score weights), so the schema isn't migrated twice. The existing local PostgreSQL demo databases are disposable.
- **Timestamps** must come back timezone-aware (UTC) on both SQLite and PostgreSQL. Fixing this on SQLite is slice D1 (overlaps QA bug #20 for `period_end`).

## 6. AI analysis requirements

- **Provider-agnostic interface**, e.g. `AnalysisProvider.generate(input_snapshot, language) -> AnalysisReport`.
  - **Demo and tests:** a deterministic mock (PL and EN), no network.
  - **Real provider [Decided]: Google Gemini, model Gemini 3.8 Flash** (per `docs/research/llm-comparison.md`: #2 on the Vals Finance Agent v2 benchmark, native JSON-schema output). Implemented **only after the demo**, with the official `google-genai` SDK (#11 picks `google-genai` instead of upgrading `openai`).
  - **Before going live:** a bake-off of 20–30 fixture analyses through Gemini 3.8 Flash, including **Polish-language quality**, measuring schema and citation-validation pass rate, real token use (including thinking tokens), cost and numeric accuracy. The Researcher's cheaper alternatives (OpenAI gpt-6-luna, Anthropic claude-haiku-5.5) may be included as baselines. The results decide whether Gemini 3.8 Flash ships as-is.
  - Notes from the research: Gemini 3.8 Flash promo pricing ($0.75/$3.75 per 1M tokens, ≈$0.013–0.024 per analysis) ends 2026-12-31 and doubles from 2027-01-01; an app used in the EEA must use the Gemini **paid** tier (no training on paid-tier data).
  - There is no silent fallback from a real provider to the mock in production.
- **Input:**
  - instrument data, stored metrics, prices and (optionally) the score breakdown;
  - 1–20 evidence items, each with a unique ID, source name and URL, "as of" date and excerpt;
  - optional user notes, marked as opinion.
  - Evidence is built from stored data with its source metadata, plus optional sources the user adds.
- **Output schema** (text in the requested language, English field names): summary, observations (each with evidence IDs), risks, scenarios `base`/`upside`/`downside`, assumptions, thesis-breakers, open questions, uncertainty, freshness warnings.
- **Validation:** the schema must match, all citations must resolve to known evidence IDs, and malformed output fails visibly.
- **Saving:** only validated reports are saved, together with the input snapshot, language, provider, model, prompt or contract version and creation time.
- **Guardrails** (from `AGENTS.md`): not financial advice, scenarios instead of buy/sell (demo phase; post-demo signal rationales follow section 12), freshness shown, nothing inferred about holdings or risk profile unless Raul explicitly includes them, and evidence and notes treated as untrusted input that cannot override the rules.
- **Cost control:** a configurable timeout and output limit. In the demo phase the request is made only on explicit user action, never in bulk or on a schedule. Post-demo, scanner-triggered AI rationales are allowed within a configured cost cap (section 12).

## 7. Data source requirements

Decision based on `docs/research/market-data-sources.md` (tested on 2026-10-08).

- **Primary [Decided]: yfinance**, upgraded from the pinned `0.2.33` to **`>=1.7`** (old versions break when Yahoo changes cookies/crumbs). Tested coverage: GPW stocks (`.WA`, back to 2000), GPW Beta ETFs, EU and US stocks, Xetra/LSE ETCs; shallow GPW fundamentals (about 4–5 years annual, about 6 quarters).
  - **Local cache and throttling:** every response is stored locally; refresh only on explicit request; throttle and batch calls; handle `YFRateLimitError` / "Too Many Requests" visibly.
  - **Own instrument type:** Yahoo types ETCs as `EQUITY`, so the app keeps its own STOCK/ETF/ETC type keyed by ISIN (manual mapping, editable in the UI).
  - **Terms:** yfinance is unofficial; Yahoo's API is "intended for personal use only". Use is limited to Raul's personal, local research; no redistribution or publishing of the data.
- **Paid fallback [Decided: documented, not implemented now]: EODHD.** EOD All-World $19.99/month covers WAR (GPW) prices; the Fundamentals plan ($59.99/month) only if deeper GPW statements are needed. Its terms explicitly allow private storage and analysis. Test exact tickers on the free key (20 calls/day) before paying.
- **Not used:** Stooq (captcha + JS gate since 2026; `pandas-datareader` can be dropped), Twelve Data (GPW only on the Ultra plan), Alpha Vantage / Marketstack (tiny free tiers, GPW unverified), FMP (restrictive download clause), Massive/Polygon (US only).
- **Collector interfaces by capability:** instrument lookup, descriptive data, price history, stock fundamentals, ETF/ETC attributes. One provider may implement only some of them. Provider-specific suffixes (e.g. `.WA`, `.DE`) stay inside the adapter.
- **Offline fake collector:** deterministic and synthetic. Used for demo and tests, selected by configuration (e.g. `DATA_COLLECTOR=fake`).
- **Provenance:** every stored value records its source, "as of" date and retrieval time.
- **Fallback [Proposal]:** a CSV import for instruments or prices; optional later: an ESEF/filings.xbrl.org importer for audited GPW annual figures.

## 8. Non-functional requirements

- **Local and private (demo phase):** loopback only; no telemetry; all data stays local. A third party receives data only when Raul explicitly triggers a real AI analysis or a data refresh. **Post-demo:** server deployment for the owner only, behind login and HTTPS; still no telemetry; scheduled scans and notifications send only what section 12 allows (section 12, #48, #56).
- **Secrets:** API keys (e.g. `GEMINI_API_KEY`) live only in a git-ignored `.env`, never in the repo, fixtures, logs or tests. GitHub secret scanning and push protection are already on. The personal default `DATABASE_URL` in `app/core/config.py` should be replaced with a neutral placeholder.
- **Data durability:** the personal PostgreSQL database (notes, theses, watchlist) is separate from the disposable SQLite demo database, schema changes go through Alembic migrations (#8–#10), and backup and export steps (`pg_dump`) are documented.
- **Offline demo:** no network access at all. HTMX, CSS and chart assets are bundled locally, not loaded from a CDN, and AI and data are faked.
- **Test rules** (from `AGENTS.md`):
  - tests for every behavior change;
  - no live market-data or AI providers in automated tests;
  - deterministic fakes;
  - run the relevant pytest suite before claiming completion.
  - The SQLite suite runs in CI with `DeprecationWarning` treated as an error. PostgreSQL tests are opt-in (#9).
- **Coverage:** **80% target**. The journal records 76% on master; PR #22 proposes raising it above 80% with a fail-under gate.
- **Code quality:** Black, isort and flake8 at 79 columns (`pyproject.toml`, `.flake8`). Linear git history (`AGENTS.md`). Explanations a learner can follow.
- **Performance [Proposal]:** pages render in under 1 second locally with up to about 500 instruments and 10 years of daily prices.
- **Localization:** PL (default) and EN UI catalogs; locale-aware number and date formatting in the UI; APIs keep ISO and machine formats. **[Proposal]** simple per-language message catalogs (or Babel/gettext) with a test that both catalogs have the same keys.

## 9. Demo definition (3–5 minutes)

**Setup:** one command (slice D2) starts a fresh SQLite demo database, seeds `demo-v2`, uses the fake collector and mock AI, binds to `127.0.0.1`, and opens `/ui`. No `.env` and no network.

1. **0:00** Instrument list in Polish: filter by type (stock, ETF, ETC) and exchange (GPW, US, EU). The "dane syntetyczne" ("synthetic data") badge and the disclaimer banner are visible. Switch to EN and back.
2. **0:45** A GPW stock's detail page: annual and quarterly metrics, missing values shown as "brak danych", a revenue and net income trend chart.
3. **1:15** The stock's score: components, weights, contributions, "as of" dates and the disclaimer; change one weight and see the score recompute.
4. **1:45** Compare the stock with a US stock and an ETF: shared metrics only, with currency and period warnings.
5. **2:15** Add two instruments to the watchlist, then open the watchlist with its "as of" dates and stale markers.
6. **2:45** Add a note and an active thesis with a thesis-breaker.
7. **3:15** Run a (mock) AI analysis in Polish, then one in English: scenarios, risks, citations that link to evidence, freshness warnings and the disclaimer. Then open the analysis history.
8. **4:00** "Refresh data" with the fake collector shows provenance updating. Close.

**Done when:** the QA Engineer's checklist passes on a clean clone, a CI job starts demo mode and requests every page in both languages, and the Code Reviewer approves the UI review.

## 10. Open questions

Resolved in v0.2:
- ~~4. Scoring in or out?~~ **Resolved: in scope** as a transparent, explainable, configurable score that is never a buy/sell signal in the demo (US6). Remaining detail moved to Q4 below.
- ~~7. UI technology?~~ **Resolved: Jinja2 + HTMX under `/ui`**, with a PL/EN switch (Polish default).
- ~~8. Personal database?~~ **Resolved: PostgreSQL** for personal data; SQLite for tests and the demo. #8–#10 stay on the main path after the demo.

Still open:
1. **AI provider rollout:** Gemini 3.8 Flash is chosen; open is the bake-off outcome (Polish quality, schema pass rate, cost after the 2027 price change). **[Proposal]** run the bake-off on `demo-v2` fixtures right after the demo; keep gpt-6-luna as the documented low-cost alternative if Gemini fails it.
2. **Data source depth:** yfinance is primary; open is whether GPW fundamentals (4–5 years) are deep enough. **[Proposal]** start with yfinance only; revisit EODHD Fundamentals or an ESEF importer only if the shallow history blocks real use.
3. **Disclaimer:** exact Polish and English wording and placement (global banner, on each analysis and score, in exports). **[Proposal]** global banner plus a short line on every analysis and score; wording reviewed by the Code Reviewer in D8.
4. **Score components and default weights:** which components per type? **[Proposal]** stocks: profitability (ROE, net margin), valuation (P/E, P/B), balance sheet (debt-to-equity, current ratio), growth (revenue YoY); ETFs/ETCs: cost (TER), size (AUM), volatility, max drawdown, tracking (when available). Equal default weights per type.
5. **ETF/ETC metrics:** which fund attributes and price metrics (TER, AUM, tracking difference, volatility, drawdown, returns over N periods)? **[Proposal]** TER, AUM, issuer, underlying, domicile, distribution policy, plus price-derived 1y/3y return, volatility and max drawdown.
6. **Cross-currency comparisons:** show native currencies only, or add FX conversion (needs an FX source)? **[Proposal]** native currencies only in v1, with a warning.
7. **Translation mechanism:** simple catalogs vs Babel/gettext. **[Proposal]** simple catalogs in v1.
8. **Money precision:** keep floats for monetary values, or move to exact `Numeric` columns? **[Proposal]** decide before #8 so the first migration gets it right. (from QA)
9. **`period_type`:** free text today; restrict to an enum such as annual/quarterly/TTM? **[Proposal]** enum, in I1. (from QA)
10. **Ticker case:** case-sensitive on `/companies` but uppercased by fetch-company; normalize everywhere? **[Proposal]** normalize in I1 (see #16, #17). (from QA)
11. **Duplicate names:** create allows the same name with a different ticker, update rejects it; which rule wins? **[Proposal]** allow duplicate names; uniqueness is `(ticker, exchange)`. (from QA)
12. **`DEBUG` default:** currently `True`, which exposes `/test-config`; default to `False`? **[Proposal]** yes. (from QA)
13. **Legacy `init_db` sample data:** repeats net income and appears to swap ROE/ROA; fix or drop it? **[Proposal]** drop in favour of the demo fixture. (from QA)

Added in v0.3 (post-demo direction, section 12):

14. **Hosting target and budget:** VPS, home server or cloud platform? Monthly budget? Public internet with login, or private network (VPN/Tailscale) plus login? (#56)
15. **Notification channel:** email, Telegram or other (Signal, push)? (#58)
16. **Signal frequency:** daily after market close, several times a day, or a weekly digest? (#58)
17. **Holdings import:** which brokers, and how: manual entry, a generic CSV, or broker-specific CSV exports? (#57)
18. **2FA:** required (TOTP with recovery codes), optional, or not needed? (#48)

## 11. Phased roadmap

Already done: #4 deprecation cleanup (PR #13), #5 CI (PR #14), #6 tooling (PR #15). In review: PR #22 coverage above 80% with a CI gate. Open QA bugs #16–#21 are fixed alongside the slices they touch (#20 with D1; #16/#17 before or with I1; #18/#21 before or with D3).

| Phase | Slices (owner) | Existing issues |
|---|---|---|
| **P1 Demo foundation** | **D1** timezone-aware UTC timestamps and foreign keys on SQLite (Dev). **D3** collector interface plus offline fake, selected by config (Dev). **D2** one-command demo mode (Dev). | #20 (overlaps D1); #7 hygiene recommendation (Code Reviewer, any time, not blocking) |
| **P2 Instrument model** | **I1** generalize `companies` to `instruments` with app-owned stock/ETF/ETC types, the `(ticker, exchange)` key and ISIN (Dev). **I2** `PriceBar` storage plus `demo-v2` fixture (Dev, QA). **I3** ETF/ETC attributes (Dev). | #16, #17 |
| **P3 UI (pure Python)** | **D4** UI skeleton with the PL/EN switch: layout, disclaimer, list and detail pages, bundled assets (Dev). **D6** trend charts (Dev). **C1** comparison view (Dev). **W1** watchlist (Dev). **N1** notes and theses (Dev). **D5** create/edit/delete forms (Dev). | D4/D5 add explicit `jinja2` and `python-multipart` pins (recorded in #11) |
| **P3b Scoring** | **S1** transparent instrument score: components, weights, freshness, configurable weights, disclaimer (Dev; Code Reviewer checks no-signal wording). After I1–I3, D4, D6, C1; before A1. | — |
| **P4 AI (mocked)** | **A1** provider interface, deterministic PL/EN mock, report schema, citation validation, saving (Dev). **A2** analysis UI and history, language follows the UI (Dev). | #12 deferred; no profile dependency |
| **P5 Demo acceptance** | **D7** demo checklist plus CI demo job (QA). **D8** UI and security review, including disclaimer and score wording (Code Reviewer). **D9** README "Run the demo" and refreshed work-state (Dev). | PR #22 coverage gate |
| **P6 Persistence and real data (after the demo)** | **#8** first Alembic migration capturing the instrument schema → **#9** opt-in PostgreSQL harness (QA) → **#10** switch to migrations. **R1** yfinance adapter with cache, throttling and the ISIN-keyed type mapping (Dev). The `yfinance>=1.7` pin itself moved with #11's security/deps part. **R2** Gemini adapter via `google-genai` plus the 20–30 analysis bake-off incl. Polish quality (Dev, QA). | `google-genai` still waits for R2. `jinja2` and `python-multipart` wait for D4/D5. #21 with R1 |
| **P7 Server, login, portfolio, signals (after P6) [Decided direction 2026-10-08]** | **#56** server deployment: hosting, HTTPS, secrets, encrypted backups (Dev, Security Engineer). **#48** authentication: login, sessions, rate limiting, 2FA [Open] (Dev, Security Engineer). **#57** portfolio holdings: model, manual/CSV import, privacy (Dev). **#58** market scanner with buy/sell/opportunity signals and notifications (Dev, Code Reviewer). | #45, #52 security baseline |

**Issue map (Demo v1, label `demo`):** D1 #23, D3 #24, D2 #25, I1 #26, I2 #27, I3 #28, D4 #29, D6 #30, C1 #31, W1 #32, N1 #33, D5 #34, S1 #35, A1 #36, A2 #37, D7 #38, D8 #39, D9 #40. Post-demo: R1 #54, R2 #55; P7 (label `deferred`): #48 authentication, #56 server deployment, #57 portfolio holdings, #58 market scanner and signals.

**Dependencies:**
- #20 ↔ D1 (same root cause on SQLite); D1 and D3 → D2.
- D1 → I1 → I2, I3; D3 → I2.
- I1 and D2 → D4 → D5, D6, C1, W1, N1; I2 → D6, C1.
- I1–I3, D4, D6, C1 → S1 → A1 → A2 (A1 hard-depends on I2; N1 is optional for A1, notes context is added once N1 is available).
- All of P1–P4 → D7 and D8 → D9.
- On 2026-10-08 the Project Manager moved #11's security/deps part ahead of the demo after the Security Engineer's review found CVEs. That part is the FastAPI and Starlette CVE upgrade, the `requests` and `python-dotenv` floors, removal of unused pins, the runtime/dev split, and the hashed lock. It is scheduled before the demo. After it: #45 and #47 together, with #50 if that fix stays small, then the remaining demo slices. Demo done → #8 → #9 → #10. `google-genai` stays with R2. `jinja2` and `python-multipart` stay with D4/D5.
- P7: #45 → #48 → #56 (no internet exposure before auth); #48 and I1 → #57; R1 (#54), R2 (#55) and S1 (#35) → #58 (optional input from #57).
- #12 stays deferred unless analysis tailoring needs it.

## 12. Post-demo direction (2026-10-08)

Raul, 2026-10-08 (translated from Polish): *"Maybe not in the demo, but later we should add some login option. By default the app should run on a server and analyze the current market situation, so it gives signals when it's worth buying or selling, or when a good company turns up. Login will be needed because I don't want anyone breaking into the app, and also because it will hold information about my current stock portfolios, which is fairly private data."*

**The demo is unchanged:** local, bound to `127.0.0.1`, no auth, no holdings, no signals, offline. Everything below starts after Demo v1 (and after P6). Issues carry the `deferred` label until then.

### 12.1 Server deployment [Decided direction; details Open] (#56)
- The app runs on a server by default, **still single-user: the owner (Raul) only**. No public sign-up, no other accounts.
- HTTPS only (reverse proxy or private network); the app stays behind the proxy; `DEBUG` off; trusted hosts set (#45).
- Secrets (AI key, DB password, session secret, notification tokens) live outside the repo and images; never logged.
- PostgreSQL on the server, not publicly reachable; scheduled **encrypted backups** with a tested restore.
- **No internet exposure before authentication (#48) is in place.**

### 12.2 Authentication [Decided direction; 2FA Open] (#48)
- Login for the single owner account (password hashed with Argon2id or bcrypt; account created by a CLI command).
- Secure sessions (`Secure`, `HttpOnly`, `SameSite` cookies, timeouts, logout), CSRF protection on forms.
- Rate limiting and lockout on login; failed attempts logged without secrets.
- **Ideally 2FA** (TOTP with recovery codes) [Open, Q18].
- All pages and API routes require auth except a minimal health check.

### 12.3 Portfolio holdings as private data [Decided direction; import Open] (#57)
- Raul's current portfolios and holdings are stored in the app and treated as **private data**: owner-scoped, only visible when logged in, never in logs, error pages or AI prompts unless Raul explicitly includes them on a request.
- Import by manual entry and/or CSV [Open, Q17]; no broker API integration or order execution.
- **Encryption at rest** (volume and/or column level) and inclusion in encrypted backups are considered and decided in #56/#57.

### 12.4 Market scanner and signals [Decided direction; rules Open] (#58)
- A **scheduled market scanner** runs on the server [frequency Open, Q16] over the watchlist, holdings and a configurable universe, within data-provider limits (R1 cache and throttling).
- It produces **buy candidate**, **sell / review** and **interesting company** signals.
- Every signal is **explainable**: triggering rules, input values with sources and as-of dates, score breakdown and version, a rationale, **risks** and what would invalidate it, plus a coverage/confidence indicator. Signals are deterministic first; an optional AI rationale (R2) follows the section 6 validation and citation rules and is never the sole basis of a signal.
- **Notifications** via a channel to be chosen [Open, Q15], with dedup/cooldown; no portfolio amounts in notifications unless Raul opts in.
- **Signals are personal decision support for Raul, not investment advice.** Every signal view and notification says so (PL/EN). Every signal shows the disclaimer in both languages. Only the "no buy/sell signal" rule is demo-only. No automated trading.
- Scanner AI rationales run within a configured monthly budget limit. The limit's value is **[Open]** for Raul.
- Holdings and portfolio data (quantity, cost, amounts) are never sent in AI prompts by default. That covers scanner rationales and any other AI prompt. A user-requested analysis may include them only when Raul explicitly includes them on that request, which is the exception already stated for holdings.
- The **score transparency principle (US6) stays**: the score remains a transparent, explainable, configurable score; signals are a separate layer built on it and on other rules.

### 12.5 What this changes in earlier sections
- Sections 1, 2, 3, 6 and 8: "no authentication/hosting", "no holdings", "no schedulers" and "never a buy/sell signal" now apply to the **demo phase only**. Section 4 (US3.1, US6): the no-buy/sell wording is demo-only; the disclaimer stays in both phases, including on post-demo signals.
- Section 5: new post-demo entities (`Portfolio`, `Holding`, `Signal`) and the demo-phase design constraint (future `owner_id`, no auth code in the demo).
- Section 10: new open questions 14–18. Section 11: new phase P7.
