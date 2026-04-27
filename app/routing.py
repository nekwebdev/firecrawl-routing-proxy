from __future__ import annotations

import time
from dataclasses import dataclass

from app.budget import TavilyBudgetGuard
from app.config import Settings
from app.logging_utils import hash_query, log_route_decision
from app.models import SearchRequest, SearchResponse
from app.providers.firecrawl_response import citations_satisfied, confidence_score
from app.providers.searxng import SearxngProvider
from app.providers.tavily import TavilyProvider

HARD_PROVIDER = "tavily"
QUICK_PROVIDER = "searxng"
FALLBACK_PROVIDER = "searxng"
REQUIRE_CITATIONS_FOR_HARD = True
ESCALATE_ON_LOW_CONFIDENCE = False
LOW_CONFIDENCE_THRESHOLD = 0.35

HARD_KEYWORDS = {
    "citation",
    "citations",
    "source",
    "sources",
    "proof",
    "reference",
    "references",
    "fact-check",
    "fact check",
    "comparison",
    "legal",
    "medical",
    "financial",
    "statistics",
    "statistical",
    "reliable sources",
}


@dataclass(frozen=True)
class RouteDecision:
    route_type: str
    primary_provider: str
    fallback_provider: str
    is_critical: bool


class RouterEngine:
    def __init__(
        self,
        settings: Settings,
        budget: TavilyBudgetGuard,
        tavily_provider: TavilyProvider,
        searxng_provider: SearxngProvider,
    ) -> None:
        self.settings = settings
        self.budget = budget
        self.tavily = tavily_provider
        self.searxng = searxng_provider

    def classify(self, query: str) -> RouteDecision:
        q = query.lower().strip()
        hard = any(word in q for word in HARD_KEYWORDS)
        long_or_complex = len(q) > 160 or q.count(" and ") + q.count(" or ") + q.count(",") >= 3
        is_hard = hard or long_or_complex

        if is_hard:
            return RouteDecision(
                route_type="hard",
                primary_provider=HARD_PROVIDER,
                fallback_provider=FALLBACK_PROVIDER,
                is_critical=True,
            )

        return RouteDecision(
            route_type="quick",
            primary_provider=QUICK_PROVIDER,
            fallback_provider=FALLBACK_PROVIDER,
            is_critical=False,
        )

    async def _search_provider(
        self,
        provider_name: str,
        req: SearchRequest,
        *,
        is_critical: bool,
    ):
        max_results = req.max_results or self.settings.default_max_results
        timeout_seconds = req.timeout or self.settings.request_timeout_seconds

        if provider_name == "tavily":
            allowed, reason = self.budget.can_use(is_critical=is_critical)
            if not allowed:
                raise RuntimeError(f"tavily_budget_blocked:{reason}")
            results = await self.tavily.search(
                req.query,
                max_results=max_results,
                timeout_seconds=timeout_seconds,
                is_critical=is_critical,
            )
            self.budget.record_call(is_critical=is_critical)
            return results

        if provider_name == "searxng":
            return await self.searxng.search(
                req.query,
                max_results=max_results,
                timeout_seconds=timeout_seconds,
                locale=req.locale,
            )

        raise RuntimeError(f"unknown_provider:{provider_name}")

    async def search(self, req: SearchRequest) -> SearchResponse:
        started = time.perf_counter()
        decision = self.classify(req.query)

        chosen_provider = decision.primary_provider
        fallback_used = False
        fail_reason = None

        try:
            data = await self._search_provider(
                decision.primary_provider, req, is_critical=decision.is_critical
            )
        except Exception as exc:
            data = []
            fail_reason = f"primary_failed:{type(exc).__name__}"

        if not data and decision.fallback_provider:
            fallback_used = True
            chosen_provider = decision.fallback_provider
            try:
                data = await self._search_provider(
                    decision.fallback_provider, req, is_critical=False
                )
            except Exception as exc:
                data = []
                fail_reason = f"fallback_failed:{type(exc).__name__}"

        if decision.route_type == "quick" and data and ESCALATE_ON_LOW_CONFIDENCE:
            if confidence_score(data) < LOW_CONFIDENCE_THRESHOLD:
                try:
                    escalated = await self._search_provider(HARD_PROVIDER, req, is_critical=False)
                except Exception:
                    escalated = []
                if escalated:
                    data = escalated
                    chosen_provider = HARD_PROVIDER
                    fallback_used = True

        citation_ok = citations_satisfied(data)
        if decision.route_type == "hard" and REQUIRE_CITATIONS_FOR_HARD and not citation_ok:
            if chosen_provider != HARD_PROVIDER:
                try:
                    retry = await self._search_provider(HARD_PROVIDER, req, is_critical=True)
                except Exception as exc:
                    retry = []
                    fail_reason = f"citation_retry_failed:{type(exc).__name__}"
                if retry:
                    data = retry
                    chosen_provider = HARD_PROVIDER
                    fallback_used = True
                    citation_ok = citations_satisfied(data)

            if not citation_ok:
                self._log(
                    decision,
                    req.query,
                    chosen_provider,
                    fallback_used,
                    started,
                    data,
                    False,
                    fail_reason,
                )
                return SearchResponse(
                    success=False, data=[], error="citations_required_not_satisfied"
                )

        self._log(
            decision,
            req.query,
            chosen_provider,
            fallback_used,
            started,
            data,
            citation_ok,
            fail_reason,
        )

        if not data:
            return SearchResponse(success=False, data=[], error=fail_reason or "no_results")
        return SearchResponse(success=True, data=data)

    def _log(
        self,
        decision: RouteDecision,
        query: str,
        chosen_provider: str,
        fallback_used: bool,
        started: float,
        data,
        citation_ok: bool,
        fail_reason: str | None,
    ) -> None:
        state = self.budget.state_snapshot()
        log_route_decision(
            {
                "query_hash": hash_query(query),
                "route_type": decision.route_type,
                "chosen_provider": chosen_provider,
                "fallback_used": fallback_used,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "result_count": len(data),
                "citation_satisfied": citation_ok,
                "fail_reason": fail_reason,
                "budget": state,
            },
            enabled=self.settings.route_decision_logging,
        )
