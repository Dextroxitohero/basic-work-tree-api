"""Signup, login, /auth/me y permisos por endpoint."""

import logging
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.models import User
from app.modules.auth.permissions import ALL_PERMISSIONS
from tests.conftest import TEST_PASSWORD

SIGNUP = {"full_name": "Ana Pérez", "email": "ana@example.com", "password": "una-clave-segura"}


async def signup(client, **overrides):
    return await client.post("/auth/signup", json=SIGNUP | overrides)


def assert_session_shape(body):
    assert set(body) == {"access_token", "token_type", "expires_in", "user"}
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 12 * 3600
    assert set(body["user"]) == {"id", "email", "full_name", "is_active", "permissions"}


# ---------------------------------------------------------------- signup


async def test_signup_creates_a_read_only_active_user(anonymous_client):
    response = await signup(anonymous_client)

    assert response.status_code == 201
    body = response.json()
    assert_session_shape(body)
    assert body["user"]["email"] == "ana@example.com"
    assert body["user"]["full_name"] == "Ana Pérez"
    assert body["user"]["is_active"] is True
    assert body["user"]["permissions"] == ["employees:read"]


async def test_signup_token_works_right_away_and_is_read_only(anonymous_client):
    token = (await signup(anonymous_client)).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    read = await anonymous_client.get("/employees", headers=headers)
    write = await anonymous_client.post("/job-titles", json={"name": "Dev"}, headers=headers)

    assert read.status_code == 200
    assert (write.status_code, write.json()["error"]) == (403, "insufficient_permissions")


@pytest.mark.parametrize(
    "extra",
    [
        {"permissions": ["employees:read", "users:write"]},
        {"permissions": ["users:write"]},
        {"is_active": True},
        {"id": str(uuid4())},
        {"is_admin": True},
    ],
)
async def test_permissions_cannot_come_from_the_signup_body(anonymous_client, extra):
    response = await signup(anonymous_client, **extra)

    assert (response.status_code, response.json()["error"]) == (422, "validation_error")
    async with AsyncSessionLocal() as session:
        assert (await session.scalars(select(User))).all() == []


async def test_email_is_stored_in_lowercase(anonymous_client):
    response = await signup(anonymous_client, email="Ana.Perez@Example.COM")

    assert response.json()["user"]["email"] == "ana.perez@example.com"


async def test_password_is_stored_hashed_and_never_returned(anonymous_client):
    response = await signup(anonymous_client)

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User))
    assert user.password_hash.startswith("$argon2id$")
    assert SIGNUP["password"] not in user.password_hash
    assert SIGNUP["password"] not in response.text
    assert "password" not in response.text


async def test_password_is_never_logged(anonymous_client, caplog):
    caplog.set_level(logging.DEBUG)

    await signup(anonymous_client)
    await signup(anonymous_client, email="otra@example.com", password="corta")  # 422
    await anonymous_client.post(
        "/auth/login", json={"email": SIGNUP["email"], "password": "clave-equivocada-1"}
    )

    for secret in (SIGNUP["password"], "corta", "clave-equivocada-1"):
        assert secret not in caplog.text


async def test_validation_error_does_not_echo_the_password(anonymous_client):
    response = await signup(anonymous_client, password="corta")

    assert response.status_code == 422
    assert "corta" not in response.text


@pytest.mark.parametrize(
    "overrides",
    [
        {"password": "1234567"},  # 7: muy corta
        {"password": "x" * 129},  # 129: demasiado larga
        {"email": "no-es-un-email"},
        {"email": ""},
        {"full_name": ""},
        {"full_name": "   "},
        {"full_name": "x" * 121},
        {"full_name": None},
        {"password": None},
    ],
)
async def test_signup_validation(anonymous_client, overrides):
    response = await signup(anonymous_client, **overrides)

    assert (response.status_code, response.json()["error"]) == (422, "validation_error")


@pytest.mark.parametrize(
    "overrides", [{"password": "12345678"}, {"password": "x" * 128}, {"full_name": "x" * 120}]
)
async def test_signup_limits_are_inclusive(anonymous_client, overrides):
    assert (await signup(anonymous_client, **overrides)).status_code == 201


@pytest.mark.parametrize("second_email", ["ana@example.com", "ANA@Example.com"])
async def test_duplicated_email_is_409_even_with_other_case(anonymous_client, second_email):
    await signup(anonymous_client)

    response = await signup(anonymous_client, email=second_email)

    assert (response.status_code, response.json()["error"]) == (409, "user_email_exists")


# ---------------------------------------------------------------- login


async def test_login_with_the_right_credentials(anonymous_client, make_user):
    user = await make_user(email="luis@example.com")

    response = await anonymous_client.post(
        "/auth/login", json={"email": "luis@example.com", "password": TEST_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert_session_shape(body)
    assert body["user"]["id"] == user["id"]
    assert body["user"]["permissions"] == list(ALL_PERMISSIONS)
    me = await anonymous_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.json() == body["user"]


async def test_login_email_is_case_insensitive(anonymous_client, make_user):
    await make_user(email="luis@example.com")

    response = await anonymous_client.post(
        "/auth/login", json={"email": "LUIS@Example.com", "password": TEST_PASSWORD}
    )

    assert response.status_code == 200


async def test_signup_then_login(anonymous_client):
    await signup(anonymous_client)

    response = await anonymous_client.post(
        "/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]}
    )

    assert response.status_code == 200


async def test_wrong_password_and_unknown_email_look_exactly_the_same(anonymous_client, make_user):
    await make_user(email="luis@example.com")

    wrong_password = await anonymous_client.post(
        "/auth/login", json={"email": "luis@example.com", "password": "otra-clave-123"}
    )
    unknown_email = await anonymous_client.post(
        "/auth/login", json={"email": "nadie@example.com", "password": "otra-clave-123"}
    )

    for response in (wrong_password, unknown_email):
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["error"] == "invalid_credentials"


async def test_disabled_account_cannot_log_in(anonymous_client, make_user):
    await make_user(email="baja@example.com", is_active=False)

    right = await anonymous_client.post(
        "/auth/login", json={"email": "baja@example.com", "password": TEST_PASSWORD}
    )
    wrong = await anonymous_client.post(
        "/auth/login", json={"email": "baja@example.com", "password": "otra-clave-123"}
    )

    assert (right.status_code, right.json()["error"]) == (403, "account_disabled")
    # Sin la contraseña correcta no se revela ni que la cuenta existe.
    assert (wrong.status_code, wrong.json()["error"]) == (401, "invalid_credentials")


@pytest.mark.parametrize(
    "body",
    [
        {"email": "no-es-un-email", "password": "x"},
        {"email": "a@example.com", "password": ""},
        {"email": "a@example.com", "password": "x" * 129},
        {"email": "a@example.com"},
        {"password": "x"},
    ],
)
async def test_login_validation(anonymous_client, body):
    response = await anonymous_client.post("/auth/login", json=body)

    assert (response.status_code, response.json()["error"]) == (422, "validation_error")


# ---------------------------------------------------------------- tokens y /auth/me


async def test_missing_or_garbage_token_is_401(anonymous_client):
    for headers in ({}, {"Authorization": "Bearer basura"}, {"Authorization": "Basic abc"}):
        response = await anonymous_client.get("/employees", headers=headers)

        assert response.status_code == 401
        assert response.json()["error"] == "invalid_token"
        assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_me_requires_a_token(anonymous_client):
    response = await anonymous_client.get("/auth/me")

    assert (response.status_code, response.json()["error"]) == (401, "invalid_token")


async def test_me_reads_permissions_from_the_database_not_from_the_token(
    client, anonymous_client, make_user
):
    reader = await make_user(permissions=["employees:read"])
    before = await anonymous_client.get("/auth/me", headers=reader["headers"])

    # Un admin le sube los permisos: el MISMO token ya refleja el cambio.
    patch = await client.patch(
        f"/users/{reader['id']}", json={"permissions": ["employees:read", "employees:write"]}
    )
    after = await anonymous_client.get("/auth/me", headers=reader["headers"])
    can_write = await anonymous_client.post(
        "/employees",
        json={
            "first_name": "A",
            "last_name": "B",
            "email": "ab@example.com",
            "hire_date": "2020-01-01",
        },
        headers=reader["headers"],
    )

    assert before.json()["permissions"] == ["employees:read"]
    assert patch.status_code == 200
    assert after.json()["permissions"] == ["employees:read", "employees:write"]
    assert can_write.status_code == 201


async def test_permissions_taken_away_apply_immediately(client, anonymous_client, make_user):
    writer = await make_user(permissions=["employees:read", "job-titles:write"])
    assert (
        await anonymous_client.post("/job-titles", json={"name": "A"}, headers=writer["headers"])
    ).status_code == 201

    await client.patch(f"/users/{writer['id']}", json={"permissions": ["employees:read"]})
    response = await anonymous_client.post(
        "/job-titles", json={"name": "B"}, headers=writer["headers"]
    )

    # El token todavía dice que puede escribir, pero la base de datos manda.
    assert (response.status_code, response.json()["error"]) == (403, "insufficient_permissions")


async def test_token_of_a_deactivated_user_is_rejected_before_it_expires(
    client, anonymous_client, make_user
):
    user = await make_user()
    assert (await anonymous_client.get("/auth/me", headers=user["headers"])).status_code == 200

    await client.patch(f"/users/{user['id']}", json={"is_active": False})

    for path in ("/auth/me", "/employees"):
        response = await anonymous_client.get(path, headers=user["headers"])
        assert (response.status_code, response.json()["error"]) == (401, "invalid_token")


async def test_token_of_a_deleted_user_is_rejected(anonymous_client, make_user):
    user = await make_user()
    async with AsyncSessionLocal.begin() as session:
        await session.execute(delete(User).where(User.id == user["id"]))

    response = await anonymous_client.get("/auth/me", headers=user["headers"])

    assert (response.status_code, response.json()["error"]) == (401, "invalid_token")


# ---------------------------------------------------------------- permisos por endpoint


@pytest.mark.parametrize(
    ("method", "path", "permission"),
    [
        ("GET", "/employees", "employees:read"),
        ("GET", "/employees/{id}", "employees:read"),
        ("GET", "/employees/{id}/reports", "employees:read"),
        ("GET", "/employees/{id}/tree", "employees:read"),
        ("POST", "/employees", "employees:write"),
        ("PATCH", "/employees/{id}", "employees:write"),
        ("DELETE", "/employees/{id}", "employees:write"),
        ("GET", "/employees/{id}/positions", "employees:read"),
        ("GET", "/employees/{id}/positions/current", "employees:read"),
        ("POST", "/employees/{id}/positions", "positions:write"),
        ("GET", "/job-titles", "employees:read"),
        ("GET", "/job-titles/{id}", "employees:read"),
        ("POST", "/job-titles", "job-titles:write"),
        ("PATCH", "/job-titles/{id}", "job-titles:write"),
        ("GET", "/departments", "employees:read"),
        ("GET", "/departments/{id}", "employees:read"),
        ("POST", "/departments", "departments:write"),
        ("PATCH", "/departments/{id}", "departments:write"),
        ("GET", "/users", "users:write"),
        ("PATCH", "/users/{id}", "users:write"),
    ],
)
async def test_every_endpoint_requires_its_permission(
    anonymous_client, make_user, method, path, permission
):
    without_it = await make_user(permissions=[p for p in ALL_PERMISSIONS if p != permission])
    only_it = await make_user(permissions=[permission])
    url = path.format(id=uuid4())

    denied = await anonymous_client.request(method, url, headers=without_it["headers"])
    allowed = await anonymous_client.request(method, url, headers=only_it["headers"])

    assert denied.status_code == 403
    assert denied.json() == {
        "error": "insufficient_permissions",
        "message": "No tienes permiso para esta operación",
        "details": {"required": permission},
    }
    # Con el permiso se pasa la autorización: 404 o 422 por el id o el body, pero no 401/403.
    assert allowed.status_code not in (401, 403)


async def test_auth_endpoints_are_public_but_me_is_not(anonymous_client):
    assert (await anonymous_client.get("/auth/me")).status_code == 401
    assert (await anonymous_client.post("/auth/login", json={})).status_code == 422
    assert (await anonymous_client.post("/auth/signup", json={})).status_code == 422
