from starlette.responses import Response

from app.core.auth_cookies import (
    USER_ACCESS_COOKIE,
    USER_REFRESH_COOKIE,
    clear_user_cookies,
    set_user_cookies,
)


def _set_cookie_headers(response: Response) -> list[str]:
    return [
        value.decode("utf-8")
        for key, value in response.raw_headers
        if key.lower() == b"set-cookie"
    ]


def test_set_user_cookies_sets_two_cookies() -> None:
    response = Response()
    set_user_cookies(response, access_token="access", refresh_token="refresh")

    headers = _set_cookie_headers(response)
    assert any(header.startswith(f"{USER_ACCESS_COOKIE}=") for header in headers)
    assert any(header.startswith(f"{USER_REFRESH_COOKIE}=") for header in headers)


def test_clear_user_cookies_deletes_two_cookies() -> None:
    response = Response()
    clear_user_cookies(response)

    headers = _set_cookie_headers(response)
    assert any(header.startswith(f"{USER_ACCESS_COOKIE}=") for header in headers)
    assert any(header.startswith(f"{USER_REFRESH_COOKIE}=") for header in headers)

