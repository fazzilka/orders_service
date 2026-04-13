from collections.abc import AsyncGenerator
from uuid import UUID

from aio_pika.abc import AbstractExchange
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cookies import USER_ACCESS_COOKIE
from app.core.security import get_user_token_service
from app.db.models.user import User
from app.db.session import async_session_maker
from app.services.users import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token/", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


def get_redis(request: Request) -> Redis:
    redis: Redis | None = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is not available",
        )
    return redis


def get_rabbit_exchange(request: Request) -> AbstractExchange:
    exchange: AbstractExchange | None = getattr(request.app.state, "rabbit_exchange", None)
    if exchange is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RabbitMQ is not available",
        )
    return exchange


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        token = request.cookies.get(USER_ACCESS_COOKIE)
    if not token:
        raise credentials_exception

    token_service = get_user_token_service()

    try:
        payload = token_service.decode(token)

        if not token_service.is_user_access(payload):
            raise credentials_exception

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise credentials_exception

        user_id = UUID(subject)
    except (JWTError, ValueError) as err:
        raise credentials_exception from err

    user = await get_user_by_id(session, user_id)
    if user is None:
        raise credentials_exception

    return user
