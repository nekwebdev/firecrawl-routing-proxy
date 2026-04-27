firecrawl-routing-proxy

Production-ready Firecrawl-compatible subset proxy. Routes search calls between Tavily (hard/citation-heavy) and SearXNG (quick/fallback), with Tavily budget guard persisted in SQLite.

Architecture summary
- API: FastAPI + Uvicorn
- Routing engine: deterministic hard/quick classifier
- Providers: Tavily + SearXNG adapters via httpx
- Budget guard: local SQLite counters (daily soft cap, monthly cap, critical reserve)
- Logging: structured route decision logs using query hash (no raw query by default)

Endpoints
- GET /healthz -> {"status":"ok"}
- POST /v1/search
  - Input subset: query (required), maxResults, timeout, locale, scrapeOptions (+ unknown fields safely ignored)
  - Output subset: success, data[], error
  - data[] entries include url/title/description|markdown|content plus source/provider when available

Routing behavior (opinionated defaults)
- hard provider: tavily
- quick provider: searxng
- fallback provider: searxng
- require citations for hard queries: true
- escalate quick low confidence: false

Execution flow
1) classify query hard/quick
2) call primary provider
3) on failure/timeout/empty, call fallback provider
4) quick-route escalation path exists but disabled by default
5) hard queries enforce citation presence; may retry via Tavily, else explicit failure

Budget logic
- Persist calls in /data/tavily_budget.sqlite3 (in container; named volume)
- Before Tavily call, evaluate:
  - TAVILY_DAILY_SOFT_CAP_CALLS
  - TAVILY_MONTHLY_CAP_CALLS
  - TAVILY_RESERVE_PERCENT_CRITICAL
- Non-critical traffic respects reserve for critical queries
- Budget state logged internally, not exposed on public API

Quickstart
1) Copy env file
   cp .env.example .env
2) Set required keys in .env
3) Local dev (without containers)
   python -m venv .venv
   . .venv/bin/activate
   pip install -e .
   pip install pytest ruff pytest-asyncio
   uvicorn app.main:app --host 0.0.0.0 --port 8080
4) Container stack
   docker compose up --build -d
5) Health check
   curl -fsS http://127.0.0.1:8082/healthz

Just commands
- just help
- just fmt
- just lint
- just test
- just check
- just build
- just up
- just down
- just logs
- just health
- just shell

Docker build caching strategy
- Dockerfile uses multi-stage build.
- Dependency wheel build in builder stage happens before app source copy.
- Runtime stage installs wheels, then copies app/ last.
- Result: changing app/*.py reuses dependency layers and avoids re-downloading packages.

ENV VAR CONTRACT (final)

| Variable | Type | Default | Required | Purpose | Safe example |
|---|---|---|---|---|---|
| LOG_LEVEL | string | INFO | no | Runtime log verbosity. | INFO |
| ROUTE_DECISION_LOGGING | bool | true | no | Enable structured route decision logs. | true |
| FIRECRAWL_API_KEY | string | (empty) | no | Optional inbound auth key for proxy endpoint. Supports Bearer or x-api-key. | fc_dev_key_123 |
| TAVILY_API_KEY | string | (empty) | yes (if Tavily route used) | Tavily provider credential. | tvly-*** |
| SEARXNG_BASE_URL | URL | http://websearch-searxng:8080 | no | Base URL for SearXNG service. | http://websearch-searxng:8080 |
| TAVILY_DAILY_SOFT_CAP_CALLS | int | 8 | no | Daily soft call budget for Tavily. | 8 |
| TAVILY_MONTHLY_CAP_CALLS | int | 150 | no | Monthly hard call cap for Tavily. | 150 |
| TAVILY_RESERVE_PERCENT_CRITICAL | int | 25 | no | Portion of daily soft cap reserved for critical routes. | 25 |

Rejected candidate vars and why
- PROXY_HOST, PROXY_PORT: container command defines stable host/port; unnecessary runtime knob.
- HARD_PROVIDER, QUICK_PROVIDER, FALLBACK_PROVIDER: intentionally opinionated routing policy.
- REQUIRE_CITATIONS_FOR_HARD: fixed policy requirement; keep hardcoded true.
- ESCALATE_ON_LOW_CONFIDENCE, LOW_CONFIDENCE_THRESHOLD: escalation intentionally off by default; threshold internal detail.
- TAVILY_TIMEOUT_SECONDS, TAVILY_MAX_RESULTS: request timeout and max results accepted from API payload or sane internals.
- SEARXNG_TIMEOUT_SECONDS, SEARXNG_MAX_RESULTS: same reasoning as Tavily tunables.
- SEARXNG_SAFE_SEARCH, SEARXNG_DEFAULT_LANG: better handled per-request (locale) or internal defaults.
- FIRECRAWL_STRICT_MODE: not needed for this compatibility subset.

Assumptions
- Firecrawl compatibility target is a practical subset, not full parity.
- SearXNG image default config is acceptable for local/private internal use.
- Optional inbound API key auth is enough for this iteration; external gateway auth/rate-limit is out of scope.
