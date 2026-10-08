# Cheapest viable LLM for Investment-AI-Companion's financial analysis feature

*Researcher, 2026-10-08 (Europe/Warsaw). Every price was re-fetched today from the URLs in the Sources section. Anything I could not verify is marked **[unverified]**. I read the repo but did not change it.*

## 1. What an "analysis" is in this repo

Sources: `README.md`, `requirements.txt`, `.env.example`, `docs/work-state.md`, `docs/superpowers/specs/2026-09-08-research-workflow-and-hardening-design.md` (repo HEAD `b2541d7`, 2026-10-07).

- **There is no LLM code yet.** `docs/work-state.md` says "source-aware AI analysis remain[s] unimplemented". The README lists OpenAI as a "planned or configured integration".
- **Planned contract** (design spec, section "Source-aware AI analysis"): `POST /api/v1/analyses/` takes a stored **investor profile** (horizon, risk tolerance, markets, allowed and excluded instruments, notes), an **instrument and its type**, and **1–20 user-supplied evidence items**. Each item has a unique ID, a source name/URL, an `as_of` date and an **excerpt**.
- **Output must be strict structured JSON:** a summary, evidence-linked observations and risks, base/upside/downside scenarios, assumptions, thesis-breakers, open questions and uncertainty. Every factual observation must cite at least one known evidence ID. The service validates the schema and the cited IDs and fails visibly on malformed output. **Strict JSON-schema support is therefore a hard requirement.**
- **Planned integration:** "a small injectable provider interface and the official OpenAI Python SDK Responses API with structured output". The documented example model is GPT-5.4 Mini.
- **Pinned SDK is stale:** `requirements.txt` pins `openai==1.3.5`, which predates the Responses API. PyPI's latest is `openai 3.26.1` (2026-10-08). The spec already notes the SDK has to be upgraded.
- The README states the app must not present output as financial advice and must show sources, freshness, assumptions and uncertainty.

## 2. Token assumptions (my estimates, not measured)

| Scenario | Input tokens | Output tokens | Rationale |
|---|---|---|---|
| **A, base** | **7,000** | **2,000** | ~1,500 for the system prompt, rules and JSON schema; ~300 for the profile snapshot; ~200 for instrument metadata; ~10 evidence excerpts × ~500 = 5,000. The report JSON has ~10 sections, so 2,000 output tokens. |
| **B, base + reasoning** | 7,000 | 5,000 | Same as A plus ~3,000 hidden reasoning tokens. Most 2026 cheap models think by default: GPT-6 Luna defaults to `reasoning.effort=medium`, Haiku 5.5 uses adaptive thinking at `medium`, Gemini bills thinking as output, and DeepSeek Flash's default mode is thinking. Reasoning tokens are billed as output. The 3,000 figure is an **assumption**; measure it. |
| **C, heavy** | 18,000 | 6,000 | 20 evidence items (the spec maximum) × ~800 tokens, plus reasoning. |

Notes: the Claude 4.7+ tokenizer "produces approximately 30% more tokens for the same text" (Anthropic pricing page), so Haiku 5.5's effective cost is roughly 1.3× what the table shows. Prompt caching of the static system prompt and schema would lower input cost further for every provider; it is not included here.

## 3. Price per 1M tokens and cost per analysis (standard / on-demand list prices, USD)

| Model | $/1M in | $/1M out | A: 7k in/2k out | per 1,000 (A) | B: 7k/5k (A + ~3k reasoning) | per 1,000 (B) | C: 18k/6k heavy | per 1,000 (C) |
|---|---|---|---|---|---|---|---|---|
| OpenAI gpt-6-luna | $0.1 | $0.5 | $0.0017 | $1.70 | $0.0032 | $3.20 | $0.0048 | $4.80 |
| OpenAI gpt-5.6-luna | $0.2 | $1.2 | $0.0038 | $3.80 | $0.0074 | $7.40 | $0.0108 | $10.80 |
| OpenAI gpt-5.4-mini (repo spec default) | $0.75 | $4.5 | $0.0142 | $14.25 | $0.0278 | $27.75 | $0.0405 | $40.50 |
| OpenAI gpt-4.1-mini (legacy) | $0.4 | $1.6 | $0.0060 | $6.00 | $0.0108 | $10.80 | $0.0168 | $16.80 |
| OpenAI gpt-4o-mini (legacy) | $0.15 | $0.6 | $0.0022 | $2.25 | $0.0040 | $4.05 | $0.0063 | $6.30 |
| Google gemini-3.8-flash (promo to 2026-12-31) | $0.75 | $3.75 | $0.0128 | $12.75 | $0.0240 | $24.00 | $0.0360 | $36.00 |
| Google gemini-3.8-flash (from 2027-01-01) | $1.5 | $7.5 | $0.0255 | $25.50 | $0.0480 | $48.00 | $0.0720 | $72.00 |
| Google gemini-3.5-flash-lite | $0.3 | $2.5 | $0.0071 | $7.10 | $0.0146 | $14.60 | $0.0204 | $20.40 |
| Google gemini-3.1-flash-lite | $0.25 | $1.5 | $0.0047 | $4.75 | $0.0092 | $9.25 | $0.0135 | $13.50 |
| Google gemini-2.5-flash-lite (older gen) | $0.1 | $0.4 | $0.0015 | $1.50 | $0.0027 | $2.70 | $0.0042 | $4.20 |
| Anthropic claude-haiku-5.5 (<=100k prompt) | $0.1 | $0.5 | $0.0017 | $1.70 | $0.0032 | $3.20 | $0.0048 | $4.80 |
| Anthropic claude-haiku-4.5 | $1 | $5 | $0.0170 | $17.00 | $0.0320 | $32.00 | $0.0480 | $48.00 |
| DeepSeek deepseek-flash V4.1 (peak) | $0.3 | $1.2 | $0.0045 | $4.50 | $0.0081 | $8.10 | $0.0126 | $12.60 |
| DeepSeek deepseek-flash V4.1 (off-peak) | $0.15 | $0.6 | $0.0022 | $2.25 | $0.0040 | $4.05 | $0.0063 | $6.30 |
| Mistral Small 4 (mistral-small-2603) | $0.15 | $0.6 | $0.0022 | $2.25 | $0.0040 | $4.05 | $0.0063 | $6.30 |
| Groq gpt-oss-120b | $0.15 | $0.6 | $0.0022 | $2.25 | $0.0040 | $4.05 | $0.0063 | $6.30 |
| Groq gpt-oss-20b | $0.075 | $0.3 | $0.0011 | $1.12 | $0.0020 | $2.02 | $0.0032 | $3.15 |
| Groq qwen3.8-27b | $0.8 | $4 | $0.0136 | $13.60 | $0.0256 | $25.60 | $0.0384 | $38.40 |
| Together gpt-oss-120B | $0.15 | $0.6 | $0.0022 | $2.25 | $0.0040 | $4.05 | $0.0063 | $6.30 |
| Together Qwen3.8 Flash | $0.15 | $0.47 | $0.0020 | $1.99 | $0.0034 | $3.40 | $0.0055 | $5.52 |
| Together/OpenRouter GLM-5.3-Flash | $0.15 | $0.5 | $0.0020 | $2.05 | $0.0036 | $3.55 | $0.0057 | $5.70 |
| OpenRouter MiMo-V2.6-Flash | $0.14 | $0.28 | $0.0015 | $1.54 | $0.0024 | $2.38 | $0.0042 | $4.20 |
| xAI grok-4.3 | $1.25 | $2.5 | $0.0138 | $13.75 | $0.0213 | $21.25 | $0.0375 | $37.50 |


Price sources: OpenAI model pages and pricing page; Gemini pricing page; Anthropic pricing page; DeepSeek pricing page; Mistral model page; Groq models page; Together pricing page; OpenRouter `/api/v1/models` (fetched 2026-10-08); xAI models page. See Sources.

Price notes:
- **Gemini 3.8 Flash** is on promotional pricing ($0.75/$3.75) **only through 2026-12-31**. It doubles to $1.50/$7.50 on 2027-01-01 (Gemini pricing page).
- **Haiku 5.5** costs $0.10/$0.50 for prompts up to 100k tokens and $0.50/$2.50 above that.
- **DeepSeek peak hours** are 01:00–04:00 and 06:00–10:00 UTC, Mon–Fri. That is 03:00–06:00 and **08:00–12:00 Warsaw time** (CEST) today. Off-peak costs half.
- **OpenAI regional (EU) processing** adds +10% for models released on or after 2026-03-05.
- **Batch or Flex** pricing (≈50% off) exists at OpenAI, Google and Anthropic (Mistral batch pricing **[unverified]**). It is a good fit for overnight or non-interactive analyses.
- MiMo-V2.6-Flash and GLM-5.3-Flash prices come from aggregator listings (OpenRouter, Together, Ollama Cloud). The first-party prices from Xiaomi and Z.ai are **[unverified]**.

## 4. Financial-reasoning quality

The best current, independent, finance-specific evidence I found is **Vals AI Finance Agent v2** (updated 2026-10-07). It has 927 expert-reviewed questions on SEC filings, the scores come from a private test set, and the metric is dealbreaker-gated partial credit. **Caveat:** it is an *agentic* benchmark (EDGAR search, web search, calculator tools). Our task is *grounded synthesis from supplied excerpts* into a fixed schema, so treat FAB as a proxy, not a direct measure. I found no current FinanceBench or FinQA leaderboard covering these 2026 models, so that evidence is **thin**.

| Model | Vals Finance Agent v2 accuracy (rank / 76) | Vals cost per test |
|---|---|---|
| Gemini 3.8 Flash | 61.44% (#2) | $2.00 |
| Gemini 3.7 Flash | 59.04% (#5) | $1.48 |
| GLM 5.3 Flash | 57.85% (#12) | $0.05 |
| MiMo V2.6 Flash | 56.28% (#17) | $0.07 |
| GPT-5.6 Luna | 55.04% (#20) | $0.28 |
| Claude Haiku 5.5 | 54.14% (#24) | $1.64 (30m49s per task, so it used far more tokens than Luna) |
| DeepSeek V4.1 Flash | 53.48% (#30) | $0.21 |
| GPT-6 Luna | 49.87% (#41) | $0.12 |
| Qwen 3.8 27B (open weights) | 48.55% (#45) | $0.75 |
| Gemini 3.5 Flash Lite | 47.44% (#49) | $0.39 |
| GPT 5.4 Mini (repo spec default) | 45.36% (#51) | $1.20 |
| Grok 4.3 | 37.73% (#62) | $0.85 |
| Mistral Medium 3.5 | 32.10% (#66) | $1.91 |
| Claude Haiku 4.5 (thinking) | 31.01% (#67) | $0.60 |
| Gemini 3.1 Flash Lite Preview | 29.99% (#69) | $0.14 |
| gpt-oss-20b/120b, Mistral Small 4, Gemma 4, gpt-4o-mini, gpt-4.1-mini | **not listed. No current finance evidence found [thin]** | n/a |

Vals' own takeaway: "Models are able to handle simple retrieval tasks, but still struggle to perform reliably on harder, multi-step financial work that relies on precise numbers." So the app's design choices are right regardless of model: compute numbers in code, validate citations, and attach freshness warnings in code.

## 5. Structured output / JSON-schema support

| Provider / runtime | Mechanism | Strict schema? | Source |
|---|---|---|---|
| OpenAI (gpt-6-luna, gpt-5.6-luna, gpt-5.4-mini, gpt-4.1-mini, gpt-4o-mini) | Structured Outputs (`text.format` json_schema in the Responses API; `response_format` in Chat Completions). The Python SDK has `parse()` helpers for Pydantic models. | **Yes**, native strict | model pages ("Structured outputs: Supported") |
| Anthropic (Haiku 5.5) | `output_config.format` json_schema with constrained decoding; `client.messages.parse(output_format=PydanticModel)` | **Yes**. Limits: numeric/length constraints such as `minimum`/`maxLength` are unsupported (the SDK moves them into descriptions); `additionalProperties:false` is required; at most 24 optional params and 16 union-typed params across schemas | structured-outputs doc |
| Google Gemini | `response_format` with mime `application/json` plus a JSON schema; Pydantic supported | **Yes** (subset of JSON Schema; supports min/max, `anyOf`, recursion) | structured-output doc |
| DeepSeek | `response_format={'type':'json_object'}` (JSON mode only). The prompt must contain the word "json"; docs warn the API "may occasionally return empty content" | **No**. Valid JSON but not schema-enforced | JSON Output doc |
| Mistral Small 4 | "Structured Outputs" feature on `/v1/chat/completions` | Supported per model page. Strict-mode guarantees **[unverified]** (docs page is JS-rendered) | model page |
| Groq | `json_schema` with `strict: true` (constrained decoding) only on gpt-oss-20b, gpt-oss-120b and qwen3.8-27b; best-effort or JSON-object mode for other models | **Yes** for those 3 models | Groq structured-outputs doc |
| OpenRouter | Passes through `response_format` / `structured_outputs` where the routed provider supports it (per-model flags in `/api/v1/models`) | Depends on provider | OpenRouter models API |
| Ollama (local) | `format` parameter takes a JSON schema (Pydantic `model_json_schema()`); also works through the OpenAI-compatible `/v1` and `parse()` | **Yes** (grammar-constrained) | Ollama blog |
| llama.cpp (local) | GBNF grammars; JSON Schema is converted to GBNF via `json_schema` or `response_format`. The schema is **not** injected into the prompt, and unsupported schema features are **skipped silently** | Yes (a subset) | llama.cpp grammars README |

## 6. Python SDK maturity (PyPI, checked 2026-10-08)

| SDK | Latest | Release count | Notes |
|---|---|---|---|
| `openai` | 3.26.1 (2026-10-08) | 444 | Official. Repo pins **1.3.5**, which must be upgraded for the Responses API. The same SDK also reaches Ollama, Groq, DeepSeek, Together and OpenRouter through `base_url` (they expose OpenAI-compatible APIs). |
| `anthropic` | 1.12.1 (2026-10-08) | 225 | Official, with Pydantic `messages.parse()`. |
| `google-genai` | 2.29.0 (2026-10-07) | 129 | Official (new Interactions API). |
| `mistralai` | 3.1.0 (2026-10-06) | 111 | Official. |
| `groq` | 1.7.0 (2026-08-26) | 54 | Official. OpenAI-compatible endpoint as well. |
| `together` | 2.40.0 | 156 | Official. |
| `ollama` | 0.6.3 (2026-09-29) | 36 | Official; pre-1.0 versioning. |
| `llama-cpp-python` | 0.3.36 | 209 | Community bindings. |

## 7. Privacy, data retention and training

| Provider | Trains on API data? | Retention | ZDR / residency |
|---|---|---|---|
| OpenAI | **No** (since 2023-03-01, unless you opt in) | Abuse-monitoring logs up to **30 days**. Responses API may persist application state when `store` is enabled, so set `store=false` (exact default retention for stored responses **[unverified]**) | ZDR / Modified Abuse Monitoring with prior approval. EU data residency (`eu.api.openai.com`) requires MAM/ZDR; +10% price |
| Anthropic | **No** by default (commercial/API) | Deleted within **30 days**. Up to 2 years if flagged for a Usage Policy violation | ZDR by agreement. `inference_geo:"us"` costs 1.1× (Claude 4.6+). Structured-output schemas are cached 24h |
| Google Gemini | Paid tier: **no**. Free tier: yes, with human review, **except in the EEA/CH/UK**, where paid-tier data terms apply to free usage too. Apps offered to EEA users **must use Paid Services** | Paid: prompts logged "for a limited period" for abuse detection (number of days **[unverified]**) | Vertex/Enterprise for more controls |
| DeepSeek | Privacy policy lists training on inputs as a use, with an opt-out right. Policy says data is collected, processed and stored **in the PRC**. Its applicability to API traffic is not spelled out **[partly unverified]** | "as long as necessary" | None found. **Weakest privacy posture for an EU user** |
| Mistral (EU company) | Paid API: no training (or opt-out toggle). **Free tier may train by default**; "Labs" models may train regardless | ZDR available on pay-as-you-go for stateless endpoints | EU vendor |
| Groq | **No** (contractually prohibited unless permitted) | Not retained by default; up to 30 days for reliability/abuse logs | ZDR self-serve for all customers |
| OpenRouter | Depends on the routed provider. An account setting can exclude providers that train | Per provider | EU in-region routing on Business/Enterprise |
| Local (Ollama / llama.cpp) | **No data leaves the machine** | You control it | n/a |

## 8. Rate limits and free tiers

- **OpenAI:** no free API tier ("Free: Not supported" on the gpt-6-luna, gpt-5.6-luna and gpt-5.4-mini pages). The lowest paid tier ("Build") allows 5,000 RPM and 2M TPM, which is far above this app's needs.
- **Google:** free tier exists (free tokens, limits shown in AI Studio; RPD resets at midnight PT). Tier 1 starts when billing is linked. Spend-based caps start at $10 per 10 minutes on Tier 1. Exact free-tier RPM numbers aren't on the public page **[unverified]**.
- **Anthropic:** new users get "a small amount of free credits". Rate limits are tiered (Start/Build/Scale); I didn't fetch the numbers **[unverified]**.
- **DeepSeek:** concurrency limit 2,500 for deepseek-flash. Pre-paid balance.
- **Groq:** developer-plan limits for gpt-oss-120b/20b are 250K TPM and 1K RPM.
- **Mistral:** free mode exists, but it may train on your data (see above).
- **Local:** no limits, bounded only by hardware throughput.

## 9. Local options (Ollama / llama.cpp)

| Model (Ollama tag) | Download size | Finance evidence | Hardware estimate **[estimate]** |
|---|---|---|---|
| `qwen3.8:27b` | 18 GB, 256K context | FAB v2 48.55% (hosted, full precision; a local Q4 quant may score lower **[unverified]**) | 24 GB VRAM GPU or 32 GB+ Apple-silicon unified memory to leave KV-cache headroom |
| `gemma4:26b` / `gemma4:31b` | 16 GB / 19 GB | None found [thin] | Same class as above |
| `gpt-oss:20b` | 14 GB, 128K context | None for FAB v2 [thin] | 16–24 GB VRAM or 24 GB+ unified memory |
| `qwen3.5:9b` (latest) | 6.6–7.6 GB | None [thin] | 8–12 GB VRAM. Fine on a typical laptop, but expect weaker reasoning |
| GLM-5.3-Flash | 321B params / 18B active. **Cloud-only on Ollama** (`:cloud`) | FAB 57.85% | Not runnable on a dev machine |

All of these support schema-constrained output through Ollama's `format` parameter or llama.cpp GBNF. Marginal API cost is $0; the real costs are hardware, electricity and much slower generation on CPU or small GPUs.

## 10. Recommendation

- **Primary: OpenAI `gpt-6-luna`.** List price is $0.10/$0.50. That is **≈$0.0017 per analysis (A) / ≈$0.0032 with reasoning (B)**, or ≈$1.70–$3.20 per 1,000 analyses. It supports native strict Structured Outputs through the Responses API, which is exactly what the repo spec plans, so it drops into the planned design with no extra SDK. OpenAI does not train on API data; logs are kept up to 30 days; EU residency is available. Caveat: its FAB v2 score (49.9%) is mid-pack. If quality evals disappoint, step up within the same SDK to `gpt-5.6-luna` (55.0% on FAB, ≈$0.0038–0.0074 per analysis). Either is 4–9× cheaper than the spec's GPT-5.4 Mini, which also scores lower on FAB (45.4%).
- **Fallback (second vendor): Anthropic `claude-haiku-5.5`.** Same list price ($0.10/$0.50), a higher FAB v2 score (54.1%), native strict JSON schema, and no training on API data. Caveats: the newer tokenizer adds ~30% tokens, the model was token-hungry on FAB ($1.64/test vs $0.12 for GPT-6 Luna), and it needs a second SDK behind the provider interface.
- **Quality ceiling:** `gemini-3.8-flash` is #2 overall on FAB v2 (61.4%) at ≈$0.013 per analysis until 2026-12-31, then ≈$0.026.
- **Local / privacy:** `qwen3.8:27b` on Ollama with the `format` JSON schema. FAB is 48.6%, roughly GPT-6 Luna level. It needs about a 24 GB GPU or a 32 GB+ Mac. With 8 GB, use `qwen3.5:9b`, but there is no finance evidence for it.
- **Avoid for this feature:** DeepSeek (JSON mode only, not schema-strict; data stored in the PRC) and the Mistral free tier (trains by default). Cheap open models via Groq or Together (gpt-oss) have strict schema support on Groq but **no current finance evidence**.
- **Before locking in:** run the same 20–30 fixture analyses (the repo already has `fixtures/demo-v1.json`) through gpt-6-luna, gpt-5.6-luna and haiku-5.5. Measure real token usage including reasoning, schema and citation-validation pass rate, and spot-check numeric accuracy.

## Sources (all fetched 2026-10-08)

Repo
- https://github.com/Waber/Investment-AI-Companion (README.md, requirements.txt, docs/work-state.md, docs/superpowers/specs/2026-09-08-research-workflow-and-hardening-design.md)

Pricing / models
- OpenAI pricing: https://developers.openai.com/api/docs/pricing
- OpenAI GPT-6 Luna: https://developers.openai.com/api/docs/models/gpt-6-luna
- OpenAI GPT-5.6 Luna: https://developers.openai.com/api/docs/models/gpt-5.6-luna
- OpenAI GPT-5.4 Mini: https://developers.openai.com/api/docs/models/gpt-5.4-mini
- OpenAI GPT-4.1 Mini: https://developers.openai.com/api/docs/models/gpt-4.1-mini
- OpenAI GPT-4o Mini: https://developers.openai.com/api/docs/models/gpt-4o-mini
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Anthropic pricing: https://platform.claude.com/docs/en/about-claude/pricing
- Anthropic models overview: https://platform.claude.com/docs/en/about-claude/models/overview
- DeepSeek pricing: https://api-docs.deepseek.com/quick_start/pricing
- Mistral Small 4: https://docs.mistral.ai/models/mistral-small-4-0-26-03
- Groq models and prices: https://console.groq.com/docs/models
- Together pricing: https://www.together.ai/pricing
- OpenRouter models API: https://openrouter.ai/api/v1/models
- xAI models: https://docs.x.ai/docs/models

Quality
- Vals AI Finance Agent v2: https://www.vals.ai/benchmarks/fabv2

Structured output
- Anthropic: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Gemini: https://ai.google.dev/gemini-api/docs/structured-output
- DeepSeek JSON mode: https://api-docs.deepseek.com/guides/json_mode
- Groq: https://console.groq.com/docs/structured-outputs
- Ollama: https://ollama.com/blog/structured-outputs
- llama.cpp GBNF / JSON Schema: https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
- OpenAI (cited by the repo spec): https://developers.openai.com/api/docs/guides/structured-outputs (not re-fetched; capability confirmed on the model pages)

Privacy / limits
- OpenAI data controls: https://developers.openai.com/api/docs/guides/your-data
- Anthropic training: https://privacy.claude.com/en/articles/7996868-is-my-data-used-for-model-training
- Anthropic retention: https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data
- Gemini API terms: https://ai.google.dev/gemini-api/terms
- Gemini rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- DeepSeek privacy policy: https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html
- Mistral privacy controls: https://docs.mistral.ai/admin/monitor-comply/privacy-data-controls and https://help.mistral.ai/en/articles/347617-do-you-use-my-user-data-to-train-your-artificial-intelligence-models
- Groq data: https://console.groq.com/docs/your-data
- OpenRouter provider logging: https://openrouter.ai/docs/guides/privacy/provider-logging

Local models / SDKs
- Ollama library: https://ollama.com/library/qwen3.8, https://ollama.com/library/gemma4, https://ollama.com/library/gpt-oss, https://ollama.com/library/qwen3.5, https://ollama.com/library/glm-5.3-flash
- PyPI JSON API: https://pypi.org/pypi/<package>/json (openai, anthropic, google-genai, mistralai, ollama, groq, together, llama-cpp-python)
