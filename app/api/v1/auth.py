from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.core.auth_cookies import USER_REFRESH_COOKIE, clear_user_cookies, set_user_cookies
from app.core.rate_limit import limiter
from app.core.security import create_access_token, create_refresh_token, get_user_token_service
from app.schemas.auth import TokenPair, UserCreate, UserLoginRequest, UserRead
from app.services.users import (
    UserAlreadyExistsError,
    authenticate_user,
    create_user,
    get_user_by_id,
)


router = APIRouter()


@router.post("/register/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, session: AsyncSession = Depends(get_db)) -> UserRead:
    try:
        user = await create_user(session, email=user_in.email, password=user_in.password)
    except UserAlreadyExistsError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    return UserRead.model_validate(user)


@router.post("/token/", response_model=TokenPair)
@limiter.limit(settings.rate_limit_token)
async def token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
) -> TokenPair:
    user = await authenticate_user(session, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=str(user.id), email=user.email)
    refresh_token = create_refresh_token(subject=str(user.id), email=user.email)
    set_user_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/token/refresh/", response_model=TokenPair)
async def refresh_token(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TokenPair:
    refresh_token = request.cookies.get(USER_REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_service = get_user_token_service()

    try:
        payload = token_service.decode(refresh_token)
    except JWTError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from err

    if not token_service.is_user_refresh(payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token rejected",
        )

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    try:
        user_id = UUID(subject)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid subject",
        ) from err

    user = await get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    email = payload.get("email")
    email_str = email if isinstance(email, str) else user.email

    access_token = token_service.create_access(user_id=subject, email=email_str)
    new_refresh_token = token_service.create_refresh(user_id=subject, email=email_str)
    set_user_cookies(response, access_token=access_token, refresh_token=new_refresh_token)
    return TokenPair(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout/", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    clear_user_cookies(response)


@router.post("/auth/user/login/", response_model=TokenPair, status_code=status.HTTP_200_OK)
async def user_login(
    data: UserLoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TokenPair:
    user = await authenticate_user(session, email=str(data.email), password=data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=str(user.id), email=user.email)
    refresh_token = create_refresh_token(subject=str(user.id), email=user.email)
    set_user_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/user/refresh/", response_model=TokenPair, status_code=status.HTTP_200_OK)
async def user_refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TokenPair:
    return await refresh_token(request=request, response=response, session=session)


@router.post("/auth/user/logout/", status_code=status.HTTP_204_NO_CONTENT)
async def user_logout(response: Response) -> None:
    clear_user_cookies(response)
