# firecrawl-routing-proxy: minimal practical env var contract (draft)

## Concise rationale
Keep runtime knobs only where operators must adapt to deployment topology (provider endpoints/credentials) and spend controls (budget caps).
Routing policy behavior should stay opinionated in code by default to avoid config drift and hard-to-debug behavior differences across environments.

## Final contract (minimal)

| name | type | default | required | purpose | safe example |
|---|---|---|---|---|---|
| `TAVILY_API_KEY` | string (secret) | none | yes | Auth for Tavily calls used on hard/critical paths and some fallbacks. | `tvly_xxxxxxxxx_redacted` |
| `SEARXNG_BASE_URL` | URL string | `http://websearch-searxng:8080` | no | Base URL for SearXNG instance (container/internal DNS differs by deploy). | `http://searxng.internal:8080` |
| `TAVILY_DAILY_SOFT_CAP_CALLS` | integer | `8` | no | Daily soft call budget for Tavily to control burn rate. | `20` |
| `TAVILY_MONTHLY_CAP_CALLS` | integer | `150` | no | Hard monthly Tavily cap to enforce top-level cost ceiling. | `500` |
| `TAVILY_RESERVE_PERCENT_CRITICAL` | integer (0-100) | `25` | no | Reserve part of daily budget for critical/hard queries. | `30` |

Notes:
- `TAVILY_API_KEY` is the only strict requirement for the intended dual-provider routing behavior.
- If omitted, Tavily paths fail and service degrades toward SearXNG-only behavior.

## Rejected candidate vars (and why)

| name | reason rejected from minimal contract |
|---|---|
| `REQUIRE_CITATIONS_FOR_HARD` | Core product policy; should remain opinionated and stable in code, not per-env toggle. |
| `ESCALATE_ON_LOW_CONFIDENCE` | Strategy/quality experiment knob; increases behavior variance across deploys. Better controlled via code/release flags, not baseline env contract. |
| `LOW_CONFIDENCE_THRESHOLD` | Coupled to the rejected escalation feature; tuning constant, not essential runtime operator control. |
| `SEARXNG_SAFE_SEARCH` | Instance-level search policy is better owned by SearXNG config or request semantics; not essential for proxy runtime viability. |
| `SEARXNG_DEFAULT_LANG` | Request can already carry language; default can remain opinionated in code (`en`) without adding contract surface. |
