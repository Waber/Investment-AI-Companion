# Market-data sources for Investment-AI-Companion (local, single-user, personal use)

_Researched 2026-10-08 (Europe/Warsaw). Every figure has a source link below. **[UNVERIFIED]** = could not confirm from a primary source or by a test on the box. Nothing was signed up for; tests used only keyless endpoints._

## 0. What the repo uses now
- `requirements.txt` pins **`yfinance==0.2.33`** and `pandas-datareader==0.10.0`. The only collector is `app/data_collectors/yahoo_finance.py` (wraps `yf.Ticker(...).info` etc.). No other market-data provider and no API keys for one in `.env.example`.
- yfinance 0.2.33 is very old; the current release is **1.7.0** (installed on the box today). Upgrade before relying on it.
- pandas-datareader's Stooq reader no longer works (Stooq now needs an API key, see §3). pandas-datareader can be dropped.

## 1. Tests run on the box (2026-10-08)

### yfinance 1.7.0 (keyless)
| Ticker | Instrument | Daily rows / first date | Yahoo `quoteType` | Annual / quarterly income-statement periods | Ratios in `.info` |
|---|---|---|---|---|---|
| PKN.WA | Orlen (GPW) | 6,883 / 2000-01-03 | EQUITY | 5 (FY2021–FY2025) / 6 (to Q2-2026) | P/E 8.4, P/B 1.19, ROE, div. yield |
| CDR.WA | CD Projekt (GPW) | 6,883 / 2000-01-03 | EQUITY | 4 (FY2022–FY2025) / 6 (to Q2-2026) | P/E 41.6, P/B 7.1, ROE |
| ETFBW20TR.WA | Beta ETF WIG20TR (GPW) | 1,940 / 2019-01-07 | ETF | n/a | n/a |
| ETFBSPXPL.WA | Beta ETF S&P500 PLN-hedged (GPW) | 1,395 / 2021-03-15 | ETF | n/a | n/a |
| 4GLD.DE | Xetra-Gold ETC (Xetra) | 4,288 / 2009-11-13 | **EQUITY** | n/a | n/a |
| PHAU.L | WisdomTree Physical Gold ETC (LSE) | 4,742 / 2008-01-02 | **EQUITY** | n/a | n/a |
| SGLN.L | iShares Physical Gold ETC (LSE) | 3,914 / 2011-04-08 | **EQUITY** | n/a | n/a |
| EUNL.DE | iShares Core MSCI World (Xetra ETF) | 4,325 / 2009-09-25 | ETF | n/a | n/a |
| AAPL | Apple (US) | 11,547 / 1980-12-12 | EQUITY | 4 / 5 | yes |
| SAP.DE / ASML.AS / MC.PA | EU stocks | 7,293 / 7,263 / 6,878 | EQUITY | 4–5 / 0–6 (MC.PA: no quarterly) | yes |

Takeaways: Yahoo covers every required market, and ETFs including Polish Beta ETFs. It also returns GPW fundamentals, but only 4–5 years annual and about 6 quarters. **ETCs come back as `EQUITY`**, so Yahoo cannot tell ETCs apart. The app needs its own instrument-type field (e.g. a manual mapping by ISIN or name).

### Twelve Data reference endpoints (keyless `/stocks`, `/etfs`, `show_plan=true`)
- GPW (MIC XWAR) is listed with **1,138 instruments**: PKN, CDR, ETFBW20TR (ETF), etc.
- **Access level for PKN.XWAR and ETFBW20TR is `"plan":"Ultra"`**. GPW data needs the Ultra plan.
- 4GLD (Xetra) and SAP (Xetra) are `Grow`. AAPL is `Basic` (free). PHAU is `Grow` on Euronext and `Pro` on Milan. ETCs are listed under `/etfs`, so there's no separate ETC type.

### EODHD (`api_token=demo`)
- `demo` only works for US samples (AAPL.US returned data). `PKN.WAR` gave `Forbidden`. GPW coverage is confirmed from EODHD's own docs and pages instead (see §2).

### Stooq
- `https://stooq.pl/q/d/l/?s=pkn&i=d` (and every other symbol tested) returned a **JavaScript proof-of-work "verify your browser" page, not CSV**. I didn't try to get around it.

### Alpha Vantage
- The `demo` key refuses SYMBOL_SEARCH for "orlen" and "cd projekt" ("demo API key is for demo purposes only"). **GPW coverage [UNVERIFIED]**.

### filings.xbrl.org (ESEF filings index, keyless)
- 877 Polish (PL) ESEF filings indexed. ORLEN has filings for FY2020–FY2023 only (none for FY2024/25 yet). Useful, but it lags.

### GPW website
- `gpw.pl` was not reachable from the box (connection reset). The archive is described from search-indexed pages only.

## 2. Comparison table

| Source | GPW stocks | EU stocks | US stocks | ETFs | ETCs | Fundamentals | GPW fundamentals | History | Free tier | Cheapest paid that meets the need | Personal-use ToS | Official? | Python |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **yfinance / Yahoo** | ✅ tested (.WA) | ✅ tested | ✅ | ✅ incl. GPW Beta ETFs | ✅ prices, but typed EQUITY | Statements (annual ~4–5y, quarterly ~5–6) + ratios | ✅ tested PKN, CDR (shallow) | GPW back to 2000; US back to 1980 | Free, no key; unofficial rate limits | n/a | Yahoo API "intended for personal use only" (yfinance README) | ❌ Unofficial; scrapes Yahoo's endpoints | `yfinance` (mature, very active) |
| **Stooq** | ✅ historically the best free GPW source | ✅ | ✅ | ✅ | ✅ | Prices only (CSV) | ❌ | Long (decades) [depth UNVERIFIED today] | Needs captcha-issued API key **plus** browser JS check (since ~Mar/Apr 2026) | n/a | No redistribution; S&P/DJ index data own non-commercial use only (per search snippet of ToS; page behind JS check) **[partly UNVERIFIED]** | Semi-official site; automation now actively discouraged | pandas-datareader reader **removed/broken** |
| **EODHD** | ✅ WAR: 612 active + 417 delisted (docs) | ✅ | ✅ | ✅ | **[UNVERIFIED]** how ETCs are typed (types: stock/ETF/fund) | Full statements + ratios (Fundamentals plan) | ✅ (e.g. KGH.WAR, PKO.WAR pages; non-US from ~2000) | EOD 30+ y (paid) | 20 calls/day, 1 y history, EOD only | **$19.99/mo** EOD All-World; **$59.99/mo** Fundamentals; $99.99 All-in-One | Non-Professional use allowed: "store, manipulate, and analyze the data for private, non-commercial purposes" | ✅ Commercial licensed vendor (FR) | Official `eodhd` SDK |
| **Twelve Data** | ⚠️ listed, but **Ultra only** (tested) | ✅ (Xetra = Grow) | ✅ (free) | ✅ | Listed as ETFs | Statements (Grow+) | GPW only on Ultra | **[UNVERIFIED]** per symbol | 8 credits/min, 800/day; US mainly | Grow from $29/mo (no GPW); **Ultra from $329/mo** for GPW | Individual plans: "personal, internal, and non-commercial purposes" | ✅ Commercial vendor | Official `twelvedata` |
| **Financial Modeling Prep** | **[UNVERIFIED]** (global only on Ultimate) | Ultimate only (UK on Premium) | ✅ | ✅ | **[UNVERIFIED]** | Strong statements + ratios | **[UNVERIFIED]** | 5 y (Starter), 30+ y (Premium/Ultimate) | 250 calls/day, EOD, US | Starter $22 (US), Premium $59 (US/UK/CA), **Ultimate $149** (global) | Personal, non-commercial license (ToS §2.2.1). The ToS also says no copying or downloading content without written approval, which is awkward for a local DB. | ✅ Commercial vendor | Community libs (e.g. `fmp_py`) |
| **Alpha Vantage** | **[UNVERIFIED]**: no official exchange list | Partial (suffixes like .LON, .DEX) | ✅ | ✅ | **[UNVERIFIED]** | Statements/overview (mainly US) **[UNVERIFIED for non-US]** | **[UNVERIFIED]** | "25+ years" | **25 requests/day** | $49.99/mo (75 req/min) | Free key: "personal, non-commercial use" | ✅ Commercial vendor; international coverage known to be patchy | `alpha_vantage` (community), official MCP |
| **Marketstack** | **[UNVERIFIED]** (70 exchanges total) | ✅ some | ✅ (US via Tiingo) | ETF holdings (paid) | **[UNVERIFIED]** | Company statements only on Business ($149.99) | **[UNVERIFIED]** | 1 y free / 10 y Basic / 15+ y Pro | 100 requests/**month**, EOD, non-commercial | Basic $9.99/mo (10k req/mo, 10 y) | Free plan marked "Non-Commercial Use" | ✅ Commercial (apilayer) | No official SDK; plain REST |
| **Massive (ex-Polygon.io)** | ❌ US only | ❌ | ✅ | ✅ (US-listed) | US-listed only | Financials & Ratios ($29/mo add-on or in Advanced) | ❌ | 2 y free, 5 y Starter, 10 y Dev, 20+ y Adv | 5 calls/min, EOD, 2 y | Starter $29/mo | "Individual use" plans | ✅ Commercial vendor | Official `massive` (formerly `polygon-api-client`) [package name **UNVERIFIED**] |
| **GPW official (gpw.pl archive)** | ✅ (official) | ❌ | ❌ | ✅ GPW ETFs | n/a | ❌ | ❌ | Daily session archive (XLS) | Free manual XLS download per date/instrument | Real-time/licensed data via vendors (GPW fee schedule 2026) | Public website; licensed redistribution needs an agreement | ✅ Official | None (XLS download; site unreachable from box) |
| **ESEF reports / filings.xbrl.org** | ✅ annual audited statements (iXBRL) | ✅ EU issuers | ❌ | ❌ | ❌ | Annual statements (raw XBRL) | ✅ authoritative, but **lags** (ORLEN to FY2023) | FY2020+ | Free, keyless JSON API | n/a | Public filings | ✅ Official filings (index run by XBRL International) | Plain REST; `arelle` for XBRL parsing |
| **ESPI/EBI (current & periodic reports)** | ✅ events/reports | ❌ | ❌ | ❌ | ❌ | Report text/PDFs, not structured | Partial (docs) | n/a | Free to read | n/a | Public | ✅ Official disclosure channel | Unofficial scraper `pyespiebipapapi` |
| **BiznesRadar / Stockwatch / Bankier / money.pl** | ✅ | partial | partial | ✅ | partial | BiznesRadar: long GPW statement history + ratios (web) | ✅ (web only) | Long | Free web; BiznesRadar Premium 432 PLN/yr (forecasts etc.) | n/a | BiznesRadar ToS: no API; account can be removed for "techniki… zakłócające pracę infrastruktury" | ❌ No API; scraping only | None |

## 3. Notes per source

**yfinance / Yahoo Finance**: Best free coverage of every required market (tested above). Caveats: (1) unofficial. The README says yfinance is "not affiliated, endorsed, or vetted by Yahoo… intended for research and educational purposes… the Yahoo! finance API is intended for personal use only." (2) Yahoo throttles (`YFRateLimitError` / "Too Many Requests") and changes cookies and crumbs, which breaks older versions. Keep yfinance up to date, cache locally, and batch calls. (3) GPW fundamentals are shallow (4–5 y annual) and come from Yahoo's data vendor, which can have gaps or errors **[quality UNVERIFIED]**. (4) ETCs are typed `EQUITY`.

**Stooq**: Used to be the go-to free GPW CSV source. Since about March/April 2026 downloads need an API key obtained via a captcha, and as of June 2026 a JavaScript browser check too (confirmed today: every CSV URL returns the JS challenge). pandas-datareader moved Stooq to "removed readers". Fine for manual one-off downloads in a browser. It's no longer a dependable automated feed, and getting around the check would go against what the site clearly intends.

**EODHD**: The only reasonably priced provider that documents GPW (WAR) coverage for prices **and** fundamentals. Paid plans: EOD All-World $19.99/mo ($199/yr), EOD+Intraday $29.99, Fundamentals $59.99 (fundamentals plan excludes EOD prices!), All-in-One $99.99. Free: 20 calls/day, 1 y, EOD only. Fundamentals cost 10 calls each. The ToS explicitly allows personal storage and analysis. The free tier is too small for production but fine for testing coverage.

**Twelve Data**: Good API and SDK, but GPW instruments need the **Ultra** plan (tested via `show_plan`), from $329/mo. Not worth it for this use case.

**FMP**: Strong US fundamentals. Global coverage only on Ultimate ($149/mo). GPW coverage unverified. The personal-use ToS forbids copying or downloading content without approval, which fits badly with a local cache.

**Alpha Vantage**: 25 requests/day free is too little. GPW coverage undocumented and international coverage historically patchy.

**Marketstack**: 100 requests/month free. GPW unverified. Statements only on the $149.99 Business plan.

**Massive (ex-Polygon.io)**: Rebranded on 2025-10-30; old api.polygon.io still works. US-only for stocks, so it doesn't fit.

**GPW-specific**: GPW publishes a free daily session archive (XLS) for shares and ETFs. That's good for official end-of-day cross-checks but not an API. Licensed GPW data goes through vendors under GPW's market-data agreement and fee schedule. For GPW fundamentals, the authoritative free source is the issuers' ESEF annual reports (indexed on filings.xbrl.org, but with a lag) and ESPI/EBI periodic reports. BiznesRadar/Stockwatch hold the richest GPW statement histories but have no API.

## 4. Recommendation
- **Primary (free): yfinance** (upgrade from 0.2.33 to ≥1.7). Covers GPW, EU and US stocks, GPW Beta ETFs, Xetra/LSE ETCs, and gives basic GPW fundamentals. Cache everything locally (SQLite/Postgres) and throttle requests.
- **Fallback / paid upgrade: EODHD**. $19.99/mo for EOD prices worldwide incl. WAR. Add the $59.99/mo Fundamentals plan only if deeper GPW statements are needed. Use the free 20-calls/day key to test the exact tickers first.
- **Combination needed?** For prices, no: yfinance alone covers everything. For **GPW fundamentals**, yfinance is shallow (4–5 y), so either pay for EODHD Fundamentals or build a small ESEF/filings.xbrl.org importer for audited annual figures (free, official, lagging). Optional: the GPW archive XLS for official EOD cross-checks.
- **ETCs**: no source tested labels ETCs separately (Yahoo: EQUITY; Twelve Data: ETF). Keep your own `instrument_type` (STOCK/ETF/ETC) keyed by ISIN in the app's DB.
- **Avoid**: Massive (US-only), Twelve Data (GPW only on Ultra), Alpha Vantage / Marketstack (tiny free tiers, GPW unverified), FMP (GPW unverified, global only $149, restrictive download clause), Stooq for automation (captcha + JS gate).

## 5. Sources (accessed 2026-10-08 unless noted)
- Repo: https://github.com/Waber/Investment-AI-Companion (requirements.txt, app/data_collectors/yahoo_finance.py)
- yfinance README/disclaimer: https://github.com/ranaroussi/yfinance (raw README) · Yahoo terms linked there: https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html
- yfinance rate limiting: https://github.com/ranaroussi/yfinance/discussions/2431 · https://github.com/ranaroussi/yfinance/issues/2526
- Stooq API-key change: https://github.com/pydata/pandas-datareader/issues/1012 (2026-04-13) · https://github.com/pydata/pandas-datareader/pull/1029 · https://opserver.de/ubb7/ubbthreads.php?Board=47&main=60441&type=thread&ubb=printthread (JS check, 2026-06) · ToS https://stooq.com/terms.html (behind JS check; content via search snippet only)
- EODHD pricing: https://eodhd.com/pricing · ToS: https://eodhd.com/financial-apis/terms-conditions · Exchange/ticker list docs (WAR 612/417): https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours · https://eodhd.com/financial-apis/covered-tickers-eodhd · GPW fundamentals examples: https://eodhd.com/financial-summary/KGH.WAR · https://eodhd.com/financial-summary/PKO.WAR
- Twelve Data pricing: https://twelvedata.com/pricing · ToS: https://twelvedata.com/terms · plan check: `https://api.twelvedata.com/stocks?symbol=PKN&exchange=XWAR&show_plan=true`
- FMP pricing: https://site.financialmodelingprep.com/pricing-plans and https://site.financialmodelingprep.com/developer/docs/pricing (prices $22/$59/$149 read from search-indexed snapshot; live page didn't render prices to the fetcher) · secondary: https://aifinhub.io/articles/financial-modeling-prep-pricing-2026/ (2026-06-17) · ToS: https://site.financialmodelingprep.com/terms-of-service · FAQ: https://site.financialmodelingprep.com/faqs
- Alpha Vantage premium: https://www.alphavantage.co/premium/ · ToS: https://www.alphavantage.co/terms_of_service/ · docs: https://www.alphavantage.co/documentation/
- Marketstack pricing: https://marketstack.com/pricing
- Massive pricing: https://massive.com/pricing?product=stocks · rebrand: https://massive.com/blog/polygon-is-now-massive/ · international: https://massive.com/knowledge-base/article/does-massive-offer-international-data
- GPW archive: https://www.gpw.pl/archiwum-notowan · ETF quotes: https://www.gpw.pl/etfy-pelna-wersja-notowan · GPW fee schedules: https://www.gpw.pl/pub/GPW/files/PDF/cennik/cennik_2026.pdf · https://www.gpw.pl/pub/GPW/files/PDF/cennik/2026_10_01_WSE_Market_Data_License_Agreement_-_Fee_Schedule.pdf
- ESEF index: https://filings.xbrl.org/api/filings?filter[country]=PL · ORLEN: https://filings.xbrl.org/api/entities/259400VVMM70CQREJT74/filings
- ESPI/EBI scraper: https://github.com/wegar-2/pyespiebipapapi
- BiznesRadar ToS: https://www.biznesradar.pl/information/terms · Premium: https://www.biznesradar.pl/premium/brpremium (432 PLN/yr per search snippet **[UNVERIFIED on page]**)
