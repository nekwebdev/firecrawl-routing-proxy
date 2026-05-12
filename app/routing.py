from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.budget import TavilyBudgetGuard
from app.config import Settings
from app.logging_utils import hash_query, log_route_decision
from app.models import SearchRequest, SearchResponse
from app.providers.firecrawl_response import citations_satisfied, confidence_score
from app.providers.searxng import SearxngProvider
from app.providers.tavily import TavilyProvider

HARD_PROVIDER = "tavily"
QUICK_PROVIDER = "searxng"
HARD_FALLBACK_PROVIDER = "searxng"
QUICK_FALLBACK_PROVIDER = "searxng"
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
                fallback_provider=HARD_FALLBACK_PROVIDER,
                is_critical=True,
            )

        return RouteDecision(
            route_type="quick",
            primary_provider=QUICK_PROVIDER,
            fallback_provider=QUICK_FALLBACK_PROVIDER,
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

    @staticmethod
    def _error_info(exc: Exception) -> tuple[str, int | None, str]:
        error_class = type(exc).__name__
        upstream_status: int | None = None

        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            upstream_status = exc.response.status_code
        elif hasattr(exc, "response") and exc.response is not None:
            upstream_status = getattr(exc.response, "status_code", None)

        detail = str(exc)
        return error_class, upstream_status, detail

    @staticmethod
    def _collapse_fail_reason(provider_attempts: list[dict[str, object]]) -> str:
        failures = [attempt for attempt in provider_attempts if not attempt["ok"]]
        if not failures:
            return "no_results"

        parts: list[str] = []
        for attempt in failures:
            provider = str(attempt["provider"])
            error_class = str(attempt["error_class"])
            upstream_status = attempt["upstream_status"]
            if upstream_status is None:
                parts.append(f"{provider}:{error_class}")
            else:
                parts.append(f"{provider}:{error_class}:{upstream_status}")
        return f"providers_failed:{','.join(parts)}"

    async def _attempt_provider(
        self,
        provider_attempts: list[dict[str, object]],
        provider_name: str,
        req: SearchRequest,
        *,
        is_critical: bool,
        phase: str,
    ):
        try:
            results = await self._search_provider(provider_name, req, is_critical=is_critical)
            provider_attempts.append(
                {
                    "provider": provider_name,
                    "phase": phase,
                    "ok": True,
                    "result_count": len(results),
                }
            )
            return results
        except Exception as exc:
            error_class, upstream_status, detail = self._error_info(exc)
            provider_attempts.append(
                {
                    "provider": provider_name,
                    "phase": phase,
                    "ok": False,
                    "error_class": error_class,
                    "upstream_status": upstream_status,
                    "detail": detail,
                }
            )
            return []

    async def search(self, req: SearchRequest) -> SearchResponse:
        started = time.perf_counter()
        decision = self.classify(req.query)

        chosen_provider = decision.primary_provider
        fallback_used = False
        provider_attempts: list[dict[str, object]] = []

        data = await self._attempt_provider(
            provider_attempts,
            decision.primary_provider,
            req,
            is_critical=decision.is_critical,
            phase="primary",
        )

        if not data and decision.fallback_provider:
            fallback_used = True
            chosen_provider = decision.fallback_provider
            data = await self._attempt_provider(
                provider_attempts,
                decision.fallback_provider,
                req,
                is_critical=False,
                phase="fallback",
            )

        if decision.route_type == "quick" and data and ESCALATE_ON_LOW_CONFIDENCE:
            if confidence_score(data) < LOW_CONFIDENCE_THRESHOLD:
                escalated = await self._attempt_provider(
                    provider_attempts,
                    HARD_PROVIDER,
                    req,
                    is_critical=False,
                    phase="escalation",
                )
                if escalated:
                    data = escalated
                    chosen_provider = HARD_PROVIDER
                    fallback_used = True

        citation_ok = citations_satisfied(data)
        if decision.route_type == "hard" and REQUIRE_CITATIONS_FOR_HARD and not citation_ok:
            if chosen_provider != HARD_PROVIDER:
                retry = await self._attempt_provider(
                    provider_attempts,
                    HARD_PROVIDER,
                    req,
                    is_critical=True,
                    phase="citation_retry",
                )
                if retry:
                    data = retry
                    chosen_provider = HARD_PROVIDER
                    fallback_used = True
                    citation_ok = citations_satisfied(data)

            if not citation_ok:
                fail_reason = self._collapse_fail_reason(provider_attempts)
                self._log(
                    decision,
                    req.query,
                    chosen_provider,
                    fallback_used,
                    started,
                    data,
                    False,
                    fail_reason,
                    provider_attempts,
                )
                return SearchResponse(
                    success=False, data={"web": []}, error="citations_required_not_satisfied"
                )

        fail_reason = self._collapse_fail_reason(provider_attempts)
        self._log(
            decision,
            req.query,
            chosen_provider,
            fallback_used,
            started,
            data,
            citation_ok,
            None if data else fail_reason,
            provider_attempts,
        )

        if not data:
            return SearchResponse(success=False, data={"web": []}, error=fail_reason)
        return SearchResponse(success=True, data={"web": data})

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
        provider_attempts: list[dict[str, object]],
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
                "provider_attempts": provider_attempts,
                "budget": state,
            },
            enabled=self.settings.route_decision_logging,
        )
