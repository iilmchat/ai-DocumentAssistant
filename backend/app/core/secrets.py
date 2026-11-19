"""T8: абстракция доступа к секретам (Vault / AWS Secrets Manager / env fallback).

Приложение продолжает работать через env — провайдер подключается, если задан
SECRETS_PROVIDER. Никакой жёсткой зависимости от облачных SDK нет.
"""

import os

from app.core.config import settings


def get_secret(name: str, default: str = "") -> str:
    provider = os.environ.get("SECRETS_PROVIDER", "").lower()
    if provider == "vault":
        import hvac  # type: ignore[import-not-found]

        client = hvac.Client(url=os.environ["VAULT_ADDR"], token=os.environ["VAULT_TOKEN"])
        data = client.secrets.kv.v2.read_secret_version(path=name)["data"]["data"]
        return str(data.get("value", default))
    if provider == "aws":
        import boto3  # type: ignore[import-not-found]

        client = boto3.client(
            "secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1")
        )
        return str(client.get_secret_value(SecretId=name)["SecretString"])
    return os.environ.get(name, default)


def database_url() -> str:
    """Позволяет переопределить DATABASE_URL через секрет-менеджер."""
    return get_secret("DATABASE_URL", settings.DATABASE_URL)
