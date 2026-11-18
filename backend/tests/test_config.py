import pytest

from app.core.config import settings
from app.services.ai_service import ensure_embedding_dim


def test_cors_origins_are_explicit():
    origins = settings.cors_origins
    assert origins
    assert "*" not in origins


def test_ensure_embedding_dim_accepts_correct_vector():
    vector = [0.0] * settings.EMBEDDING_DIM
    assert ensure_embedding_dim(vector) is vector


def test_ensure_embedding_dim_rejects_wrong_vector():
    with pytest.raises(ValueError, match="dimension mismatch"):
        ensure_embedding_dim([0.0])
