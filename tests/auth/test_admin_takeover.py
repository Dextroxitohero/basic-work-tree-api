"""Nadie puede convertirse en administrador registrándose antes que el administrador."""

import logging

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models import User
from app.modules.auth.exceptions import UserEmailExistsError
from app.modules.auth.service import AuthService
from app.seed.admin import ensure_admin
from tests.auth.test_service import FakeHasher, FakeTokens, InMemoryUsers
from tests.conftest import TEST_PASSWORD

ADMIN_EMAIL = "admin@example.com"  # ADMIN_EMAIL de conftest, normalizado


async def all_users() -> list[User]:
    async with AsyncSessionLocal() as session:
        return list((await session.scalars(select(User))).all())


async def run_ensure_admin() -> str:
    async with AsyncSessionLocal.begin() as session:
        return await ensure_admin(session)


# ---------------------------------------------------------------- por HTTP


@pytest.mark.parametrize("email", [ADMIN_EMAIL, "ADMIN@example.com", "Admin@Example.COM"])
async def test_signup_with_the_admin_email_is_refused(anonymous_client, email):
    response = await anonymous_client.post(
        "/auth/signup",
        json={"full_name": "Intruso", "email": email, "password": "una-clave-segura"},
    )

    # Mismo error que con cualquier email ya registrado: no delata cuál es el del admin.
    assert (response.status_code, response.json()["error"]) == (409, "user_email_exists")
    assert await all_users() == []


async def test_the_pre_registration_attack_gets_nothing(anonymous_client):
    # El atacante intenta registrar el email del admin ANTES de que el admin exista...
    attack = await anonymous_client.post(
        "/auth/signup",
        json={"full_name": "Intruso", "email": ADMIN_EMAIL, "password": "clave-del-atacante"},
    )
    # ...y luego arranca la API, que crea al admin de verdad.
    status = await run_ensure_admin()

    login_as_attacker = await anonymous_client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": "clave-del-atacante"}
    )
    login_as_admin = await anonymous_client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": "contraseña-del-admin-123"}
    )
    assert attack.status_code == 409
    assert status == "created"
    assert login_as_attacker.status_code == 401
    assert login_as_admin.status_code == 200


# ---------------------------------------------------------------- ensure_admin


async def test_a_normal_account_with_the_admin_email_is_not_promoted(
    anonymous_client, make_user, password_hash, caplog
):
    # Cuenta que entró por otra vía (otra versión, otro entorno, una fila escrita a mano...).
    await make_user(email=ADMIN_EMAIL, permissions=["employees:read"])
    caplog.set_level(logging.ERROR)

    status = await run_ensure_admin()

    (user,) = await all_users()
    assert status == "conflict"
    assert user.permissions == ["employees:read"]
    assert user.is_seed_admin is False
    assert user.password_hash == password_hash  # no se toca nada
    assert "ADMIN_EMAIL" in caplog.text  # y se avisa con claridad


async def test_a_deactivated_normal_account_is_not_reactivated(anonymous_client, make_user):
    await make_user(email=ADMIN_EMAIL, permissions=["employees:read"], is_active=False)

    assert await run_ensure_admin() == "conflict"

    (user,) = await all_users()
    assert user.is_active is False


async def test_startup_does_not_crash_on_the_conflict(anonymous_client, make_user):
    # Si fallara, registrar ese email serviría para tumbar la API en cada arranque.
    await make_user(email=ADMIN_EMAIL, permissions=["employees:read"])

    async with app.router.lifespan_context(app):
        pass

    (user,) = await all_users()
    assert user.permissions == ["employees:read"]


async def test_the_seeded_admin_is_marked_and_still_restored(anonymous_client):
    assert await run_ensure_admin() == "created"
    assert await run_ensure_admin() == "unchanged"
    (admin,) = await all_users()
    assert admin.is_seed_admin is True

    async with AsyncSessionLocal.begin() as session:
        user = await session.get(User, admin.id)
        user.is_active = False
        user.permissions = []

    assert await run_ensure_admin() == "restored"
    (restored,) = await all_users()
    assert restored.is_active is True
    assert len(restored.permissions) == 6


async def test_the_seeded_admin_can_log_in_with_the_configured_password(anonymous_client):
    await run_ensure_admin()

    response = await anonymous_client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": "contraseña-del-admin-123"}
    )

    assert response.status_code == 200
    assert TEST_PASSWORD not in response.text


# ---------------------------------------------------------------- servicio (unitario)


class RecordingHasher(FakeHasher):
    def __init__(self) -> None:
        super().__init__()
        self.hashed: list[str] = []

    async def hash(self, password: str) -> str:
        self.hashed.append(password)
        return await super().hash(password)


def make_service(reserved=frozenset({ADMIN_EMAIL})):
    users, hasher = InMemoryUsers(), RecordingHasher()
    return AuthService(users, hasher, FakeTokens(), reserved_emails=reserved), users, hasher


async def test_reserved_signup_costs_the_same_hash_as_a_taken_email():
    service, users, hasher = make_service()

    with pytest.raises(UserEmailExistsError):
        await service.signup(full_name="X", email="Admin@Example.com", password="clave-12345")

    # El hash se calculó igual que en un registro normal: el tiempo no delata el email.
    assert hasher.hashed == ["clave-12345"]
    assert users.rows == {}


async def test_other_emails_are_not_reserved():
    service, users, _ = make_service()

    await service.signup(full_name="Ana", email="ana@example.com", password="clave-12345")

    assert len(users.rows) == 1


async def test_ensure_admin_statuses():
    service, users, _ = make_service()

    first = await service.ensure_admin(email=ADMIN_EMAIL, password="clave-del-admin-1")
    second = await service.ensure_admin(email=ADMIN_EMAIL, password="clave-del-admin-1")
    (admin,) = users.rows.values()
    admin.is_active = False
    third = await service.ensure_admin(email=ADMIN_EMAIL, password="clave-del-admin-1")

    assert (first, second, third) == ("created", "unchanged", "restored")
    assert admin.is_seed_admin is True


async def test_ensure_admin_refuses_a_non_seed_account():
    service, users, _ = make_service(reserved=frozenset())
    session = await service.signup(
        full_name="Ana", email=ADMIN_EMAIL, password="clave-del-atacante"
    )

    status = await service.ensure_admin(email=ADMIN_EMAIL, password="clave-del-admin-1")

    assert status == "conflict"
    assert session.user.permissions == ["employees:read"]
    assert session.user.password_hash == "hash:clave-del-atacante"
    assert len(users.rows) == 1
