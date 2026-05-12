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
                "data": {
                    "web": [
                        {
                            "url": "https://example.com",
                            "title": "Example",
                            "description": "desc",
                            "source": "https://example.com",
                            "provider": "searxng",
                        }
                    ]
                },
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
    assert isinstance(body["data"], dict)
    assert isinstance(body["data"]["web"], list)
    item = body["data"]["web"][0]
    assert item["url"] == "https://example.com"
    assert item["provider"] == "searxng"


def test_v2_search_alias_uses_same_handler(monkeypatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    app = create_app()

    class FakeRouter:
        async def search(self, payload):
            return {
                "success": True,
                "data": {
                    "web": [
                        {
                            "url": "https://example.com/v2",
                            "title": "Example V2",
                            "source": "https://example.com/v2",
                            "provider": "searxng",
                        }
                    ]
                },
            }

    app.state.router_engine = FakeRouter()
    client = TestClient(app)

    response = client.post("/v2/search", json={"query": "hello"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["web"][0]["url"] == "https://example.com/v2"


def test_search_response_matches_firecrawl_v2_sdk_shape(monkeypatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    app = create_app()

    class FakeRouter:
        async def search(self, payload):
            return {
                "success": True,
                "data": {
                    "web": [
                        {
                            "url": "https://example.com/sdk",
                            "title": "SDK",
                            "source": "https://example.com/sdk",
                            "provider": "searxng",
                        }
                    ]
                },
            }

    app.state.router_engine = FakeRouter()
    client = TestClient(app)

    response = client.post("/v2/search", json={"query": "hello"})
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "success": True,
        "data": {
            "web": [
                {
                    "url": "https://example.com/sdk",
                    "title": "SDK",
                    "description": None,
                    "markdown": None,
                    "content": None,
                    "metadata": None,
                    "source": "https://example.com/sdk",
                    "provider": "searxng",
                }
            ]
        },
        "error": None,
    }


def test_v1_v2_parity_same_payload_same_response(monkeypatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    app = create_app()

    class FakeRouter:
        async def search(self, payload):
            return {
                "success": True,
                "data": {
                    "web": [
                        {
                            "url": f"https://example.com/{payload.query}",
                            "title": "Parity",
                            "source": f"https://example.com/{payload.query}",
                            "provider": "searxng",
                        }
                    ]
                },
            }

    app.state.router_engine = FakeRouter()
    client = TestClient(app)

    payload = {"query": "same", "maxResults": 3, "locale": "en"}
    r1 = client.post("/v1/search", json=payload)
    r2 = client.post("/v2/search", json=payload)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == r2.json()


def test_malformed_input_returns_clear_error(monkeypatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "")
    client = TestClient(create_app())
    response = client.post("/v1/search", json={"maxResults": 2})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(part.get("loc") == ["body", "query"] for part in detail)
