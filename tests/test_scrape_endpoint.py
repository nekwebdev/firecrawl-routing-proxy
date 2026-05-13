from fastapi.testclient import TestClient

from app.main import create_app


def test_v2_scrape_returns_firecrawl_document_shape(monkeypatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    app = create_app()

    class FakeScraper:
        async def scrape(self, payload):
            assert payload.url == "https://example.com/page"
            assert payload.formats == ["markdown", "html"]
            return {
                "success": True,
                "data": {
                    "markdown": "# Example\n\nHello world",
                    "html": "<h1>Example</h1><p>Hello world</p>",
                    "metadata": {
                        "title": "Example",
                        "sourceURL": "https://example.com/page",
                        "statusCode": 200,
                    },
                },
                "error": None,
            }

    app.state.scrape_service = FakeScraper()
    client = TestClient(app)

    response = client.post(
        "/v2/scrape",
        json={"url": "https://example.com/page", "formats": ["markdown", "html"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "markdown": "# Example\n\nHello world",
            "html": "<h1>Example</h1><p>Hello world</p>",
            "metadata": {
                "title": "Example",
                "description": None,
                "sourceURL": "https://example.com/page",
                "url": None,
                "statusCode": 200,
                "contentType": None,
            },
        },
        "error": None,
    }


def test_v2_scrape_rejects_non_http_urls(monkeypatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    client = TestClient(create_app())

    response = client.post("/v2/scrape", json={"url": "file:///etc/passwd"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "url"]


def test_v2_scrape_requires_auth_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "secret")
    client = TestClient(create_app())

    response = client.post("/v2/scrape", json={"url": "https://example.com"})

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_api_key"
