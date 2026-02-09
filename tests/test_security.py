from uuid import uuid4

from app.core.security import get_password_hash, get_user_token_service, verify_password


def test_password_hash_roundtrip() -> None:
    password = "password123"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_password_hash_supports_long_passwords() -> None:
    password = "x" * 200
    hashed = get_password_hash(password)

    assert verify_password(password, hashed) is True


def test_user_token_service_access_and_refresh_claims() -> None:
    user_id = str(uuid4())
    email = "user@example.com"

    token_service = get_user_token_service()

    access_token = token_service.create_access(user_id=user_id, email=email)
    access_payload = token_service.decode(access_token)

    assert access_payload["sub"] == user_id
    assert access_payload["typ"] == "access"
    assert access_payload["role"] == "user"
    assert access_payload["email"] == email
    assert isinstance(access_payload.get("iat"), int)
    assert isinstance(access_payload.get("exp"), int)
    assert token_service.is_user_access(access_payload) is True
    assert token_service.is_user_refresh(access_payload) is False

    refresh_token = token_service.create_refresh(user_id=user_id, email=email)
    refresh_payload = token_service.decode(refresh_token)

    assert refresh_payload["sub"] == user_id
    assert refresh_payload["typ"] == "refresh"
    assert refresh_payload["role"] == "user"
    assert refresh_payload["email"] == email
    assert token_service.is_user_refresh(refresh_payload) is True
    assert token_service.is_user_access(refresh_payload) is False

