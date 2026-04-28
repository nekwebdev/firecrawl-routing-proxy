from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException

from app.budget import TavilyBudgetGuard
from app.config import DEFAULT_BUDGET_DB_PATH, Settings
from app.models import SearchRequest, SearchResponse
from app.providers.searxng import SearxngProvider
from app.providers.tavily import TavilyProvider
from app.routing import RouterEngine


def _api_key_ok(settings: Settings, authorization: str | None, x_api_key: str | None) -> bool:
    if not settings.firecrawl_api_key:
        return True
    bearer = ""
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()
    return settings.firecrawl_api_key in {bearer, x_api_key or ""}


def create_app() -> FastAPI:
    settings = Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    budget = TavilyBudgetGuard(
        db_path=str(Path(DEFAULT_BUDGET_DB_PATH)),
        daily_soft_cap_calls=settings.tavily_daily_soft_cap_calls,
        monthly_cap_calls=settings.tavily_monthly_cap_calls,
        reserve_percent_critical=settings.tavily_reserve_percent_critical,
    )

    app = FastAPI(title="firecrawl-routing-proxy", version="0.1.0")
    app.state.router_engine = RouterEngine(
        settings=settings,
        budget=budget,
        tavily_provider=TavilyProvider(settings),
        searxng_provider=SearxngProvider(settings),
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/search", response_model=SearchResponse)
    @app.post("/v2/search", response_model=SearchResponse)
    async def search(
        payload: SearchRequest,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None, alias="x-api-key"),
    ) -> SearchResponse:
        if not _api_key_ok(settings, authorization, x_api_key):
            raise HTTPException(status_code=401, detail="invalid_api_key")
        return await app.state.router_engine.search(payload)

    return app


app = create_app()
