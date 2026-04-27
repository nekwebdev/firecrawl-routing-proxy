from app.providers.firecrawl_response import citations_satisfied, normalize_results


def test_searx_result_without_explicit_source_fails_citation_gate() -> None:
    items = normalize_results(
        [
            {
                "url": "https://example.com/article",
                "title": "Example",
            }
        ],
        provider="searxng",
    )
    assert items
    assert items[0].source is None
    assert citations_satisfied(items) is False


def test_tavily_url_counts_as_source() -> None:
    items = normalize_results(
        [
            {
                "url": "https://example.com/article",
                "title": "Example",
            }
        ],
        provider="tavily",
    )
    assert items
    assert items[0].source == "https://example.com/article"
    assert citations_satisfied(items) is True
