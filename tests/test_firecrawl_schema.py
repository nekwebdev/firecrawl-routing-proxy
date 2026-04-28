from fastapi.testclient import TestClient

from app.main import create_app


def test_firecrawl_subset_schema_and_ignores_unknown(monkeypatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    app = create_app()

    class FakeRouter:
        async def search(self, payload):
            assert payload.query == "hello"
            assert payload.max_results == 2
            assert payload.locale == "en-US"
            return {
                "success": True,
                "data": [
                    {
                        "url": "https://example.com",
                        "title": "Example",
                        "description": "desc",
                        "source": "https://example.com",
                        "provider": "searxng",
                    }
                ],
            }

    app.state.router_engine = FakeRouter()
    client = TestClient(app)

    response = client.post(
        "/v1/search",
        json={
            "query": "hello",
            "maxResults": 2,
            "locale": "en-US",
            "scrapeOptions": {"formats": ["markdown"]},
            "unknown": "ignored",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    item = body["data"][0]
    assert item["url"] == "https://example.com"
    assert item["provider"] == "searxng"


def test_v2_search_alias_uses_same_handler(monkeypatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    app = create_app()

    class FakeRouter:
        async def search(self, payload):
            return {
                "success": True,
                "data": [
                    {
                        "url": "https://example.com/v2",
                        "title": "Example V2",
                        "source": "https://example.com/v2",
                        "provider": "searxng",
                    }
                ],
            }

    app.state.router_engine = FakeRouter()
    client = TestClient(app)

    response = client.post("/v2/search", json={"query": "hello"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"][0]["url"] == "https://example.com/v2"


def test_malformed_input_returns_clear_error(monkeypatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    client = TestClient(create_app())
    response = client.post("/v1/search", json={"maxResults": 2})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(part.get("loc") == ["body", "query"] for part in detail)
