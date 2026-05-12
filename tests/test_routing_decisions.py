from pathlib import Path

import httpx
import pytest

from app.budget import TavilyBudgetGuard
from app.config import Settings
from app.models import SearchRequest, SearchResult
from app.routing import RouterEngine


class FakeTavily:
    def __init__(self, results=None, should_fail=False):
        self.results = results or []
        self.should_fail = should_fail

    async def search(
        self, query: str, max_results: int, *, timeout_seconds: float, is_critical: bool = False
    ):
        if self.should_fail:
            raise RuntimeError("boom")
        return self.results[:max_results]


class FakeSearxng:
    def __init__(self, results=None, should_fail=False):
        self.results = results or []
        self.should_fail = should_fail

    async def search(
        self, query: str, max_results: int, *, timeout_seconds: float, locale: str | None = None
    ):
        if self.should_fail:
            raise RuntimeError("boom")
        return self.results[:max_results]


class FakeSearxngHttp403:
    async def search(
        self, query: str, max_results: int, *, timeout_seconds: float, locale: str | None = None
    ):
        request = httpx.Request("GET", "http://websearch-searxng:8080/search")
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("403 Forbidden", request=request, response=response)


class FakeSearxngFailThenSuccess:
    def __init__(self, results=None):
        self.results = results or []
        self.calls = 0

    async def search(
        self, query: str, max_results: int, *, timeout_seconds: float, locale: str | None = None
    ):
        self.calls += 1
        if self.calls == 1:
            request = httpx.Request("GET", "http://websearch-searxng:8080/search")
            response = httpx.Response(403, request=request)
            raise httpx.HTTPStatusError("403 Forbidden", request=request, response=response)
        return self.results[:max_results]


def make_settings() -> Settings:
    return Settings(TAVILY_API_KEY="***")


def make_budget(tmp_path: Path) -> TavilyBudgetGuard:
    return TavilyBudgetGuard(
        db_path=str(tmp_path / "budget.sqlite3"),
        daily_soft_cap_calls=8,
        monthly_cap_calls=150,
        reserve_percent_critical=25,
    )


@pytest.mark.asyncio
async def test_hard_query_prefers_tavily(tmp_path: Path) -> None:
    tavily_results = [
        SearchResult(
            url="https://a.com",
            title="A",
            description="x",
            source="https://a.com",
            provider="tavily",
        )
    ]
    engine = RouterEngine(
        settings=make_settings(),
        budget=make_budget(tmp_path),
        tavily_provider=FakeTavily(results=tavily_results),
        searxng_provider=FakeSearxng(results=[]),
    )

    result = await engine.search(SearchRequest(query="Need legal citations for this claim"))
    assert result.success is True
    assert result.data.web[0].provider == "tavily"


@pytest.mark.asyncio
async def test_fallback_to_searxng_when_tavily_fails(tmp_path: Path) -> None:
    searx_results = [
        SearchResult(
            url="https://b.com",
            title="B",
            description="x",
            source="https://b.com",
            provider="searxng",
        )
    ]
    engine = RouterEngine(
        settings=make_settings(),
        budget=make_budget(tmp_path),
        tavily_provider=FakeTavily(should_fail=True),
        searxng_provider=FakeSearxng(results=searx_results),
    )

    result = await engine.search(SearchRequest(query="fact check this statement with sources"))
    assert result.success is True
    assert result.data.web[0].provider == "searxng"


@pytest.mark.asyncio
async def test_hard_query_fails_without_citations(tmp_path: Path) -> None:
    no_citation = [SearchResult(url="https://c.com", title="C", source=None, provider="searxng")]
    engine = RouterEngine(
        settings=make_settings(),
        budget=make_budget(tmp_path),
        tavily_provider=FakeTavily(results=[]),
        searxng_provider=FakeSearxng(results=no_citation),
    )

    result = await engine.search(SearchRequest(query="medical references for treatment"))
    assert result.success is False
    assert result.error == "citations_required_not_satisfied"


@pytest.mark.asyncio
async def test_quick_query_retries_searxng_after_403_and_can_succeed(tmp_path: Path) -> None:
    searx_results = [
        SearchResult(
            url="https://fallback.example.com",
            title="Retry ok",
            description="ok",
            source="https://fallback.example.com",
            provider="searxng",
        )
    ]
    searx = FakeSearxngFailThenSuccess(results=searx_results)
    engine = RouterEngine(
        settings=make_settings(),
        budget=make_budget(tmp_path),
        tavily_provider=FakeTavily(results=[]),
        searxng_provider=searx,
    )

    result = await engine.search(SearchRequest(query="quick query"))
    assert result.success is True
    assert result.data.web[0].provider == "searxng"


@pytest.mark.asyncio
async def test_quick_query_structured_error_when_searxng_primary_and_retry_fail(
    tmp_path: Path,
) -> None:
    engine = RouterEngine(
        settings=make_settings(),
        budget=make_budget(tmp_path),
        tavily_provider=FakeTavily(should_fail=True),
        searxng_provider=FakeSearxngHttp403(),
    )

    result = await engine.search(SearchRequest(query="quick query"))
    assert result.success is False
    assert result.error is not None
    assert result.error.startswith("providers_failed:")
    assert result.error.count("searxng:HTTPStatusError:403") == 2
