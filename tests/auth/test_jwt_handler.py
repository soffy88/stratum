"""Tests for stratum.auth.jwt_handler — ≥8 tests per §3.7."""

import time
import jwt as pyjwt
import pytest
from stratum.auth.jwt_handler import encode_access, decode_access, SECRET_KEY, ALGORITHM
from stratum.auth.exceptions import TokenExpired, InvalidToken


def test_encode_decode_roundtrip():
    token = encode_access("user123", "corpus_user123")
    payload = decode_access(token)
    assert payload["sub"] == "user123"
    assert payload["corpus_id"] == "corpus_user123"


def test_payload_contains_required_claims():
    token = encode_access("u1", "c1")
    payload = decode_access(token)
    assert "sub" in payload
    assert "corpus_id" in payload
    assert "exp" in payload
    assert "iat" in payload


def test_expired_token_raises():
    payload = {
        "sub": "u1",
        "corpus_id": "c1",
        "exp": int(time.time()) - 100,
        "iat": int(time.time()) - 200,
    }
    token = pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    with pytest.raises(TokenExpired):
        decode_access(token)


def test_invalid_signature_raises():
    token = pyjwt.encode(
        {"sub": "u1", "corpus_id": "c1", "exp": int(time.time()) + 600, "iat": int(time.time())},
        "wrong-secret",
        algorithm=ALGORITHM,
    )
    with pytest.raises(InvalidToken):
        decode_access(token)


def test_wrong_algorithm_raises():
    token = pyjwt.encode(
        {"sub": "u1", "corpus_id": "c1", "exp": int(time.time()) + 600},
        SECRET_KEY,
        algorithm="HS384",
    )
    with pytest.raises(InvalidToken):
        decode_access(token)


def test_malformed_token_raises():
    with pytest.raises(InvalidToken):
        decode_access("not.a.valid.token.at.all")


def test_empty_token_raises():
    with pytest.raises(InvalidToken):
        decode_access("")


def test_token_without_sub_still_decodes():
    """decode_access doesn't validate claims presence, just signature+expiry."""
    payload = {"corpus_id": "c1", "exp": int(time.time()) + 600, "iat": int(time.time())}
    token = pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    result = decode_access(token)
    assert result.get("sub") is None
    assert result["corpus_id"] == "c1"


def test_encode_different_users_produce_different_tokens():
    t1 = encode_access("user_a", "corpus_a")
    t2 = encode_access("user_b", "corpus_b")
    assert t1 != t2


def test_old_jwt_secret_remains_verifiable_during_rotation(monkeypatch):
    from stratum.auth import jwt_handler

    new_secret = "new-rotation-secret-12345678901234567890"
    monkeypatch.setenv("JWT_SECRETS", f"{new_secret},{SECRET_KEY}")
    old_token = pyjwt.encode(
        {"sub": "legacy", "corpus_id": "c1", "exp": int(time.time()) + 600},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    assert jwt_handler.decode_access(old_token)["sub"] == "legacy"
    new_token = jwt_handler.encode_access("new", "c1")
    assert jwt_handler.decode_access(new_token)["sub"] == "new"


def test_service_layer_token_rotation_uses_new_key_and_accepts_old(monkeypatch):
    from stratum.common import create_token, verify_token

    new_secret = "service-rotation-secret-123456789012345678"
    monkeypatch.setenv("JWT_SECRETS", f"{new_secret},{SECRET_KEY}")
    token = create_token("service-user")
    assert verify_token(token) == "service-user"
    old_token = pyjwt.encode(
        {"sub": "legacy-service", "exp": int(time.time()) + 600},
        SECRET_KEY,
        algorithm="HS256",
    )
    assert verify_token(old_token) == "legacy-service"
