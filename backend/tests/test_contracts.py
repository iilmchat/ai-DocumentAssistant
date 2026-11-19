"""T10: контрактные тесты OpenAPI (schemathesis).

Проверяем, что эндпоинты не возвращают 500 на невалидных данных и что схема актуальна.
Запускается отдельно: `python -m pytest tests/test_contracts.py`
(или `schemathesis run http://localhost:8000/openapi.json` на стейдже).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_openapi_schema_available():
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    data = schema.json()
    assert data["info"]["title"] == "AI Document Assistant"
    assert "/api/v1/auth/login" in data["paths"]
    assert "/api/v1/chat/ask" in data["paths"]
    assert "/api/v1/organizations" in data["paths"]


def test_invalid_login_returns_422_not_500():
    # T8: мутирующие запросы требуют CSRF (double-submit cookie)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": 123, "password": None},
        headers={"X-CSRF-Token": "test"},
        cookies={"csrf_token": "test"},
    )
    assert response.status_code in (400, 403, 422)
    assert response.status_code < 500


def test_invalid_chat_request_returns_422():
    response = client.post(
        "/api/v1/chat/ask",
        json={"document_id": "not-a-uuid", "question": ""},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code in (401, 422)
    assert response.status_code < 500


def test_all_paths_have_schemas():
    data = client.get("/openapi.json").json()
    for path, methods in data["paths"].items():
        for method, spec in methods.items():
            if method not in {"get", "post", "delete", "put", "patch"}:
                continue
            responses = spec.get("responses", {})
            assert any(code.startswith("2") for code in responses), (path, method)
