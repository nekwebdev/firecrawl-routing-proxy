from __future__ import annotations

import httpx

from app.config import Settings
from app.providers.firecrawl_response import normalize_results


class TavilyProvider:
    name = "tavily"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def search(
        self,
        query: str,
        max_results: int,
        *,
        timeout_seconds: float,
        is_critical: bool = False,
    ) -> list:
        if not self.settings.tavily_api_key:
            raise RuntimeError("TAVILY_API_KEY is not configured")

        payload = {
            "api_key": self.settings.tavily_api_key,
            "query": query,
            "max_results": max_results,
            "include_raw_content": True,
            "search_depth": "advanced" if is_critical else "basic",
        }
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post("https://api.tavily.com/search", json=payload)
            response.raise_for_status()
            data = response.json()
        results = data.get("results") if isinstance(data, dict) else []
        return normalize_results(results if isinstance(results, list) else [], provider=self.name)
