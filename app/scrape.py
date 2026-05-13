from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx

from app.config import Settings
from app.models import ScrapeRequest, ScrapeResponse


class _ReadableHtmlParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title: str | None = None
        self.description: str | None = None
        self._title_parts: list[str] = []
        self._meta_attrs: dict[str, str] = {}
        self._skip_depth = 0
        self._tag_stack: list[str] = []
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()
        self._tag_stack.append(tag)
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "meta":
            name = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            content = attrs_dict.get("content", "")
            if name in {"description", "og:description"} and content and not self.description:
                self.description = html.unescape(content).strip()
        elif tag in {"p", "div", "section", "article", "header", "footer", "main", "br"}:
            self._parts.append("\n")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            self._parts.append("\n" + "#" * level + " ")
        elif tag == "li":
            self._parts.append("\n- ")
        elif tag == "a":
            href = attrs_dict.get("href")
            if href:
                self._meta_attrs["href"] = urljoin(self.base_url, href)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title" and self._title_parts and not self.title:
            self.title = _collapse_ws("".join(self._title_parts))
        if tag in {"p", "div", "section", "article", "li"}:
            self._parts.append("\n")
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        current_tag = self._tag_stack[-1] if self._tag_stack else ""
        if current_tag == "title":
            self._title_parts.append(data)
            return
        text = _collapse_ws(data)
        if text:
            self._parts.append(text + " ")

    @property
    def markdown(self) -> str:
        text = "".join(self._parts)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return html.unescape(text).strip()


def _collapse_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _decode_response_text(response: httpx.Response) -> str:
    encoding = response.encoding or "utf-8"
    return response.content.decode(encoding, errors="replace")


class ScrapeService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def scrape(self, req: ScrapeRequest) -> ScrapeResponse:
        timeout_seconds = req.timeout or self.settings.request_timeout_seconds
        headers = {
            "User-Agent": "firecrawl-routing-proxy/0.1",
            **(req.headers or {}),
        }
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.get(req.url, headers=headers)
        response.raise_for_status()

        body = _decode_response_text(response)
        content_type = response.headers.get("content-type", "")
        parser = _ReadableHtmlParser(str(response.url))
        if "html" in content_type.lower() or "<html" in body[:2048].lower():
            parser.feed(body)
            markdown = parser.markdown
            title = parser.title
            description = parser.description
        else:
            markdown = body.strip()
            title = None
            description = None

        formats = set(req.formats)
        data = {
            "markdown": markdown if "markdown" in formats else None,
            "html": body if "html" in formats else None,
            "metadata": {
                "title": title,
                "description": description,
                "sourceURL": str(response.url),
                "url": str(response.url),
                "statusCode": response.status_code,
                "contentType": content_type or None,
            },
        }
        return ScrapeResponse(success=True, data=data, error=None)
