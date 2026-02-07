import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

import bcrypt
from jose import jwt

from app.core.config import settings


TokenType = Literal["access", "refresh"]


class JwtProvider:
    def __init__(self) -> None:
        self._secret = settings.jwt_secret_key
        self._algorithm = settings.jwt_algorithm

    def encode(
        self,
        *,
        sub: str,
        token_type: TokenType,
        expires_delta: timedelta,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": sub,
            "typ": token_type,
            "iat": int(now.timestamp()),
            "exp": int((now + expires_delta).timestamp()),
        }

        if extra_claims:
            payload.update(extra_claims)

        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return cast(str, token)

    def decode(self, token: str) -> dict[str, Any]:
        payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        return cast(dict[str, Any], payload)


_jwt_provider: JwtProvider | None = None


def get_jwt_provider() -> JwtProvider:
    global _jwt_provider
    if _jwt_provider is None:
        _jwt_provider = JwtProvider()
    return _jwt_provider


class UserTokenService:
    def __init__(self, provider: JwtProvider | None = None) -> None:
        self._provider = provider or get_jwt_provider()
        self._access_ttl = timedelta(minutes=settings.access_token_expire_minutes)
        self._refresh_ttl = timedelta(days=settings.refresh_token_expire_days)

    def create_access(self, *, user_id: str, email: str) -> str:
        return self._provider.encode(
            sub=user_id,
            token_type="access",
            expires_delta=self._access_ttl,
            extra_claims={"role": "user", "email": email},
        )

    def create_refresh(self, *, user_id: str, email: str) -> str:
        return self._provider.encode(
            sub=user_id,
            token_type="refresh",
            expires_delta=self._refresh_ttl,
            extra_claims={"role": "user", "email": email},
        )

    def decode(self, token: str) -> dict[str, Any]:
        return self._provider.decode(token)

    def is_user_access(self, payload: dict[str, Any]) -> bool:
        return payload.get("typ") == "access" and payload.get("role") == "user"

    def is_user_refresh(self, payload: dict[str, Any]) -> bool:
        return payload.get("typ") == "refresh" and payload.get("role") == "user"


_user_token_service: UserTokenService | None = None


def get_user_token_service() -> UserTokenService:
    global _user_token_service
    if _user_token_service is None:
        _user_token_service = UserTokenService()
    return _user_token_service


def get_password_hash(password: str) -> str:
    prehashed = hashlib.sha256(password.encode("utf-8")).digest()
    hashed = bcrypt.hashpw(prehashed, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    plain_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")

    # Backward compatibility: accept existing bcrypt hashes of the raw password (if any).
    try:
        if bcrypt.checkpw(plain_bytes, hashed_bytes):
            return True
    except ValueError:
        pass

    prehashed = hashlib.sha256(plain_bytes).digest()
    try:
        return bcrypt.checkpw(prehashed, hashed_bytes)
    except ValueError:
        return False


def create_access_token(*, subject: str, email: str) -> str:
    return get_user_token_service().create_access(user_id=subject, email=email)


def create_refresh_token(*, subject: str, email: str) -> str:
    return get_user_token_service().create_refresh(user_id=subject, email=email)


def decode_access_token(token: str) -> dict[str, Any]:
    return get_jwt_provider().decode(token)
