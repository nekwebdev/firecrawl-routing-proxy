from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    query: str = Field(min_length=1)
    max_results: int | None = Field(default=None, alias="maxResults", ge=1, le=20)
    timeout: float | None = Field(default=None, ge=0.1, le=60)
    locale: str | None = None
    scrape_options: dict[str, Any] | None = Field(default=None, alias="scrapeOptions")


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    title: str | None = None
    description: str | None = None
    markdown: str | None = None
    content: str | None = None
    metadata: dict[str, Any] | None = None
    source: str | None = None
    provider: str | None = None


class SearchResponseData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    web: list[SearchResult] = Field(default_factory=list)


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    data: SearchResponseData = Field(default_factory=SearchResponseData)
    error: str | None = None
