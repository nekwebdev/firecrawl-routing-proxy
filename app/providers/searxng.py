from __future__ import annotations

import httpx

from app.config import Settings
from app.providers.firecrawl_response import normalize_results


class SearxngProvider:
    name = "searxng"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def search(
        self,
        query: str,
        max_results: int,
        *,
        timeout_seconds: float,
        locale: str | None = None,
    ) -> list:
        params = {
            "q": query,
            "format": "json",
            "language": locale or "en",
        }
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(
                f"{self.settings.searxng_base_url.rstrip('/')}/search",
                params=params,
                headers={
                    "User-Agent": "firecrawl-routing-proxy/0.1",
                    "X-Forwarded-For": "127.0.0.1",
                    "X-Real-IP": "127.0.0.1",
                },
            )
            response.raise_for_status()
            data = response.json()
        results = data.get("results") if isinstance(data, dict) else []
        normalized = normalize_results(
            results if isinstance(results, list) else [], provider=self.name
        )
        return normalized[:max_results]
