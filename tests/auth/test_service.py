"""Tests unitarios del servicio: sin HTTP y sin base de datos, gracias a los puertos."""

from uuid import UUID, uuid4

import pytest

from app.modules.auth.exceptions import (
    AccountDisabledError,
    InvalidCredentialsError,
    InvalidTokenError,
    LastAdminError,
    UserEmailExistsError,
)
from app.modules.auth.models import User
from app.modules.auth.permissions import ALL_PERMISSIONS
from app.modules.auth.service import AuthService


class InMemoryUsers:
    """Cumple el Protocol UserStore sin heredar de él."""

    def __init__(self) -> None:
        self.rows: dict[UUID, User] = {}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.rows.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.rows.values() if u.email == email), None)

    async def list_page(self, **_):
        raise NotImplementedError

    async def count_other_active_admins(self, user_id: UUID) -> int:
        return sum(
            1
            for u in self.rows.values()
            if u.id != user_id and u.is_active and "users:write" in u.permissions
        )

    async def lock_users(self) -> None:
        pass

    async def save(self, user: User) -> User:
        if any(u.email == user.email and u.id != user.id for u in self.rows.values()):
            raise UserEmailExistsError()
        user.id = user.id or uuid4()
        self.rows[user.id] = user
        return user


class FakeHasher:
    def __init__(self) -> None:
        self.verified: list[str | None] = []

    async def hash(self, password: str) -> str:
        return f"hash:{password}"

    async def verify(self, password: str, password_hash: str | None) -> bool:
        self.verified.append(password_hash)
        return password_hash == f"hash:{password}"


class FakeTokens:
    def issue(self, user: User) -> tuple[str, int]:
        return f"token-de-{user.email}", 60


def make_service() -> tuple[AuthService, InMemoryUsers, FakeHasher]:
    users, hasher = InMemoryUsers(), FakeHasher()
    return AuthService(users, hasher, FakeTokens()), users, hasher


async def test_signup_only_grants_read_and_lowercases_the_email():
    service, users, _ = make_service()

    session = await service.signup(full_name="Ana", email="ANA@Example.com", password="secreta-123")

    assert session.user.email == "ana@example.com"
    assert session.user.permissions == ["employees:read"]
    assert session.user.password_hash == "hash:secreta-123"
    assert (session.access_token, session.expires_in) == ("token-de-ana@example.com", 60)
    assert len(users.rows) == 1


async def test_login_verifies_a_password_even_when_the_email_does_not_exist():
    service, _, hasher = make_service()

    with pytest.raises(InvalidCredentialsError):
        await service.login(email="nadie@example.com", password="lo-que-sea-123")

    assert hasher.verified == [None]  # se hizo el trabajo de verificación igualmente


async def test_login_errors():
    service, users, _ = make_service()
    await service.signup(full_name="Ana", email="ana@example.com", password="secreta-123")

    with pytest.raises(InvalidCredentialsError):
        await service.login(email="ana@example.com", password="otra-clave-123")
    users.rows[next(iter(users.rows))].is_active = False
    with pytest.raises(AccountDisabledError):
        await service.login(email="ana@example.com", password="secreta-123")
    with pytest.raises(InvalidCredentialsError):  # sin la contraseña no se revela el estado
        await service.login(email="ana@example.com", password="otra-clave-123")


async def test_authenticate_rejects_unknown_and_inactive_users():
    service, users, _ = make_service()
    session = await service.signup(full_name="Ana", email="ana@example.com", password="secreta-123")

    assert await service.authenticate(session.user.id) is session.user
    session.user.is_active = False
    with pytest.raises(InvalidTokenError):
        await service.authenticate(session.user.id)
    with pytest.raises(InvalidTokenError):
        await service.authenticate(uuid4())
    assert len(users.rows) == 1


async def test_update_user_protects_the_last_admin():
    service, _, _ = make_service()
    await service.ensure_admin(email="admin@example.com", password="clave-del-admin-1")
    admin = (await service.login(email="admin@example.com", password="clave-del-admin-1")).user

    with pytest.raises(LastAdminError):
        await service.update_user(admin.id, {"is_active": False})
    with pytest.raises(LastAdminError):
        await service.update_user(admin.id, {"permissions": ["employees:read"]})
    kept = await service.update_user(admin.id, {"permissions": ["users:write"]})

    assert kept.permissions == ["users:write"]


async def test_ensure_admin_is_idempotent_and_restores_without_touching_the_password():
    service, users, _ = make_service()

    await service.ensure_admin(email="Admin@Example.com", password="clave-del-admin-1")
    await service.ensure_admin(email="admin@example.com", password="otra-distinta-12")
    (admin,) = users.rows.values()
    admin.is_active = False
    admin.permissions = ["employees:read"]
    await service.ensure_admin(email="admin@example.com", password="otra-distinta-12")

    assert len(users.rows) == 1
    assert admin.is_active is True
    assert set(admin.permissions) == set(ALL_PERMISSIONS)
    assert admin.password_hash == "hash:clave-del-admin-1"
