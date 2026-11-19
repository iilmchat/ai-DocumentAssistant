"""T7: нагрузочный сценарий (реальный стек, cookie-аутентификация).

Запуск:
    cd backend && locust -f tests/load/locustfile.py --host http://localhost:8000 --headless \
      --users 20 --spawn-rate 5 --run-time 2m --html ../docs/operations/reports/load.html

Каждый виртуальный пользователь логинится при старте (токен живёт 15 минут),
затем выполняет типичные операции с RAG-документом.
"""

import os

from locust import HttpUser, between, task


class DocumentAssistantUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        self.document_id = os.environ.get("LOAD_DOCUMENT_ID", "")
        token = os.environ.get("LOAD_ACCESS_TOKEN", "")

        if token:
            # Один выданный токен на всех пользователей: бэкенд принимает Bearer,
            # CSRF для Bearer не требуется (иначе rate-limit логина с одного IP).
            self.client.headers.update({"Authorization": f"Bearer {token}"})
            self.csrf = ""
            return

        email = os.environ.get("LOAD_EMAIL", "py-smoke@example.com")
        password = os.environ.get("LOAD_PASSWORD", "secret123")
        with self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
            name="/auth/login",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"login failed: {resp.status_code}")

        self.csrf = ""
        for cookie in self.client.cookies:  # RequestsCookieJar — итерируется напрямую
            if cookie.name == "csrf_token":
                self.csrf = cookie.value

    def _csrf_headers(self) -> dict[str, str]:
        return {"X-CSRF-Token": self.csrf} if self.csrf else {}

    @task(5)
    def health(self):
        self.client.get("/health/live", name="/health/live")

    @task(3)
    def list_documents(self):
        self.client.get("/api/v1/documents/?limit=20", name="/documents/?limit=20")

    @task(2)
    def ask_question(self):
        if not self.document_id:
            return
        self.client.post(
            "/api/v1/chat/ask",
            json={
                "document_id": self.document_id,
                "question": "Какие сроки оплаты указаны в документе?",
                "top_k": 5,
            },
            headers=self._csrf_headers(),
            name="/chat/ask",
        )

    @task(1)
    def progress(self):
        if not self.document_id:
            return
        self.client.get(
            f"/api/v1/documents/{self.document_id}/progress",
            name="/documents/{id}/progress",
        )
