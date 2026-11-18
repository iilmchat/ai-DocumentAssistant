from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("secret123", "not-a-hash")


def test_access_token_roundtrip():
    token = create_access_token("123e4567-e89b-12d3-a456-426614174000")
    assert decode_access_token(token) == "123e4567-e89b-12d3-a456-426614174000"


def test_invalid_token_returns_none():
    assert decode_access_token("garbage") is None
