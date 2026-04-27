from __future__ import annotations

from urllib.parse import urlparse

from app.models import SearchResult


def _is_http_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _extract_source(item: dict, provider: str, url: str) -> str | None:
    direct = item.get("source") or item.get("source_url")
    if _is_http_url(direct):
        return direct

    sources = item.get("sources")
    if isinstance(sources, list):
        for candidate in sources:
            if _is_http_url(candidate):
                return candidate

    # Tavily URLs are typically the citation target; allow as source there.
    if provider == "tavily" and _is_http_url(url):
        return url

    return None


def normalize_results(raw_items: list[dict], provider: str) -> list[SearchResult]:
    out: list[SearchResult] = []
    for item in raw_items:
        url = item.get("url") or item.get("link")
        if not _is_http_url(url):
            continue
        source = _extract_source(item, provider=provider, url=url)
        out.append(
            SearchResult(
                url=url,
                title=item.get("title"),
                description=item.get("description") or item.get("snippet"),
                markdown=item.get("markdown"),
                content=item.get("content") or item.get("raw_content"),
                metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else None,
                source=source,
                provider=provider,
            )
        )
    return out


def citations_satisfied(items: list[SearchResult]) -> bool:
    if not items:
        return False
    return all(_is_http_url(item.source) for item in items)


def confidence_score(items: list[SearchResult]) -> float:
    if not items:
        return 0.0
    score = 0.0
    for item in items[:5]:
        local = 0.0
        if item.title:
            local += 0.35
        if item.description or item.content:
            local += 0.35
        if _is_http_url(item.source):
            local += 0.30
        score += local
    return max(0.0, min(1.0, score / min(len(items), 5)))
