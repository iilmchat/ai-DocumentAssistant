"""S3: нагрузочный сценарий. Запуск:
    cd backend && locust -f tests/load/locustfile.py --host http://localhost
Токен и document_id задаются через env: LOAD_ACCESS_TOKEN, LOAD_DOCUMENT_ID.
"""

import os
import uuid

from locust import HttpUser, between, task


class DocumentAssistantUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        self.token = os.environ.get("LOAD_ACCESS_TOKEN", "")
        self.document_id = os.environ.get("LOAD_DOCUMENT_ID", "")
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})

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
                "question": f"Кратко опиши документ {uuid.uuid4().hex[:6]}",
                "top_k": 5,
            },
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
