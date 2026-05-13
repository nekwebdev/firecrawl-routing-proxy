from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    query: str = Field(min_length=1)
    max_results: int | None = Field(default=None, alias="maxResults", ge=1, le=20)
    limit: int | None = Field(default=None, ge=1, le=20)
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


class FirecrawlSearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    title: str | None = None
    description: str | None = None
    category: str | None = None


class FirecrawlSearchResponseData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    web: list[FirecrawlSearchResult] = Field(default_factory=list)


class FirecrawlSearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    data: FirecrawlSearchResponseData = Field(default_factory=FirecrawlSearchResponseData)
    error: str | None = None


class ScrapeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    url: str
    formats: list[str] = Field(default_factory=lambda: ["markdown"])
    headers: dict[str, str] | None = None
    timeout: float | None = Field(default=None, ge=0.1, le=120)
    only_main_content: bool | None = Field(default=None, alias="onlyMainContent")

    @field_validator("url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute http(s) URL")
        return value

    @field_validator("formats")
    @classmethod
    def normalize_formats(cls, value: list[str]) -> list[str]:
        allowed = {"markdown", "html"}
        normalized = [item for item in value if item in allowed]
        return normalized or ["markdown"]


class ScrapeMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    title: str | None = None
    description: str | None = None
    source_url: str = Field(alias="sourceURL")
    url: str | None = None
    status_code: int | None = Field(default=None, alias="statusCode")
    content_type: str | None = Field(default=None, alias="contentType")


class ScrapeDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    markdown: str | None = None
    html: str | None = None
    metadata: ScrapeMetadata


class ScrapeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    data: ScrapeDocument | None = None
    error: str | None = None
