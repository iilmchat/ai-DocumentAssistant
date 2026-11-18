from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_cors_allows_configured_origin():
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unknown_origin():
    response = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_liveness():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_request_id_header_is_propagated():
    response = client.get("/health", headers={"X-Request-ID": "test-request-id"})
    assert response.headers["X-Request-ID"] == "test-request-id"


def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text


def test_readiness_with_mocked_dependencies():
    conn = AsyncMock()
    conn.execute.return_value = MagicMock(all=lambda: [])
    engine = MagicMock()
    engine.begin.return_value.__aenter__ = AsyncMock(return_value=conn)
    engine.begin.return_value.__aexit__ = AsyncMock(return_value=None)
    redis = AsyncMock()
    redis.ping.return_value = True

    with (
        patch("app.core.database.engine", engine),
        patch.object(main, "redis_client", redis),
    ):
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"] == {"db": "ok", "redis": "ok"}
