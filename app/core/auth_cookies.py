from fastapi import Response

from app.core.config import settings

USER_ACCESS_COOKIE = "user_access_token"
USER_REFRESH_COOKIE = "user_refresh_token"


def set_user_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=USER_ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=USER_REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )


def clear_user_cookies(response: Response) -> None:
    response.delete_cookie(USER_ACCESS_COOKIE, path="/")
    response.delete_cookie(USER_REFRESH_COOKIE, path="/")
