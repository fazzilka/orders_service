from uuid import UUID

import pytest

from app.core.auth_cookies import USER_ACCESS_COOKIE, USER_REFRESH_COOKIE
from app.core.security import create_refresh_token


def _cookie_names(client) -> set[str]:
    return {cookie.name for cookie in client.cookies.jar}


@pytest.fixture()
def _override_db(app):
    import app.api.v1.auth as auth_module

    async def override_get_db():
        yield object()

    app.dependency_overrides[auth_module.get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def test_register_success(client, fake_user, monkeypatch, _override_db):
    import app.api.v1.auth as auth_module

    async def fake_create_user(session, email: str, password: str):
        return fake_user

    monkeypatch.setattr(auth_module, "create_user", fake_create_user)

    response = client.post(
        "/register/",
        json={"email": fake_user.email, "password": "password123"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == fake_user.email
    assert "id" in payload
    assert "created_at" in payload


def test_register_conflict(client, monkeypatch, _override_db):
    import app.api.v1.auth as auth_module
    from app.services.users import UserAlreadyExistsError

    async def fake_create_user(session, email: str, password: str):
        raise UserAlreadyExistsError

    monkeypatch.setattr(auth_module, "create_user", fake_create_user)

    response = client.post(
        "/register/",
        json={"email": "user@example.com", "password": "password123"},
    )

    assert response.status_code == 409


def test_token_success_returns_pair_and_sets_cookies(
    client, fake_user, monkeypatch, _override_db
):
    import app.api.v1.auth as auth_module

    async def fake_authenticate_user(session, email: str, password: str):  # type: ignore[no-untyped-def]
        return fake_user

    monkeypatch.setattr(auth_module, "authenticate_user", fake_authenticate_user)

    response = client.post(
        "/token/",
        data={"username": fake_user.email, "password": "password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert isinstance(payload["access_token"], str) and payload["access_token"]
    assert isinstance(payload["refresh_token"], str) and payload["refresh_token"]

    assert client.cookies.get(USER_ACCESS_COOKIE)
    assert client.cookies.get(USER_REFRESH_COOKIE)


def test_token_invalid_credentials_returns_401(
    client, monkeypatch, _override_db
):
    import app.api.v1.auth as auth_module

    async def fake_authenticate_user(session, email: str, password: str):
        return None

    monkeypatch.setattr(auth_module, "authenticate_user", fake_authenticate_user)

    response = client.post(
        "/token/",
        data={"username": "user@example.com", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 401


def test_refresh_missing_cookie_returns_401(client, _override_db):
    response = client.post("/token/refresh/")
    assert response.status_code == 401


def test_refresh_success_sets_new_pair_and_cookies(
    client, fake_user, monkeypatch, _override_db
):
    import app.api.v1.auth as auth_module

    async def fake_get_user_by_id(session, user_id: UUID):
        return fake_user

    monkeypatch.setattr(auth_module, "get_user_by_id", fake_get_user_by_id)

    refresh_token = create_refresh_token(subject=str(fake_user.id), email=fake_user.email)
    client.cookies.set(USER_REFRESH_COOKIE, refresh_token, domain="testserver.local", path="/")

    response = client.post("/token/refresh/")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload["access_token"], str) and payload["access_token"]
    assert isinstance(payload["refresh_token"], str) and payload["refresh_token"]

    assert USER_ACCESS_COOKIE in _cookie_names(client)
    assert USER_REFRESH_COOKIE in _cookie_names(client)


def test_logout_clears_cookies(client, _override_db):
    client.cookies.set(USER_ACCESS_COOKIE, "access", domain="testserver.local", path="/")
    client.cookies.set(USER_REFRESH_COOKIE, "refresh", domain="testserver.local", path="/")

    response = client.post("/logout/")

    assert response.status_code == 204

    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(
        header.startswith(f"{USER_ACCESS_COOKIE}=") and "Max-Age=0" in header
        for header in set_cookie_headers
    )
    assert any(
        header.startswith(f"{USER_REFRESH_COOKIE}=") and "Max-Age=0" in header
        for header in set_cookie_headers
    )
