from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.core.security import get_password_hash, verify_password
from app.db.models.user import User


class UserAlreadyExistsError(Exception):
    pass


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = (
        select(User)
        .options(load_only(User.id, User.email, User.hashed_password))
        .where(User.email == email)
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    stmt = select(User).options(load_only(User.id, User.email)).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalars().first()


async def create_user(session: AsyncSession, email: str, password: str) -> User:
    user = User(email=email, hashed_password=get_password_hash(password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise UserAlreadyExistsError from exc
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(session, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
