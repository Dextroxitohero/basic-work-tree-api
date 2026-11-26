"""Administrador sembrado a partir de ADMIN_EMAIL y ADMIN_PASSWORD."""

from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.models import User
from app.modules.auth.permissions import ALL_PERMISSIONS
from app.seed.admin import ensure_admin

ADMIN_EMAIL = "admin@example.com"  # ADMIN_EMAIL de conftest, normalizado a minúsculas
ADMIN_PASSWORD = "contraseña-del-admin-123"


async def run_ensure_admin() -> None:
    async with AsyncSessionLocal.begin() as session:
        await ensure_admin(session)


async def all_users() -> list[User]:
    async with AsyncSessionLocal() as session:
        return list((await session.scalars(select(User))).all())


async def test_admin_exists_after_seeding_twice(anonymous_client):
    await run_ensure_admin()
    await run_ensure_admin()

    users = await all_users()
    assert len(users) == 1
    assert users[0].email == ADMIN_EMAIL
    assert users[0].is_active is True
    assert set(users[0].permissions) == set(ALL_PERMISSIONS)
    assert users[0].password_hash.startswith("$argon2id$")
    assert ADMIN_PASSWORD not in users[0].password_hash


async def test_the_seeded_admin_can_log_in_and_manage_users(anonymous_client):
    await run_ensure_admin()

    login = await anonymous_client.post(
        "/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    users = await anonymous_client.get("/users", headers=headers)

    assert login.status_code == 200
    assert set(login.json()["user"]["permissions"]) == set(ALL_PERMISSIONS)
    assert users.status_code == 200


async def test_existing_admin_is_restored_without_touching_its_password(anonymous_client):
    await run_ensure_admin()
    async with AsyncSessionLocal.begin() as session:
        await session.execute(
            update(User).values(
                is_active=False, permissions=["employees:read"], password_hash="hash-elegido"
            )
        )

    await run_ensure_admin()

    (admin,) = await all_users()
    assert admin.is_active is True
    assert set(admin.permissions) == set(ALL_PERMISSIONS)
    assert admin.password_hash == "hash-elegido"  # la contraseña que él eligió se respeta


async def test_a_healthy_admin_is_not_modified(anonymous_client):
    await run_ensure_admin()
    (before,) = await all_users()

    await run_ensure_admin()

    (after,) = await all_users()
    assert (after.id, after.updated_at, after.password_hash) == (
        before.id,
        before.updated_at,
        before.password_hash,
    )


async def test_other_users_are_not_touched(anonymous_client, make_user):
    other = await make_user(permissions=["employees:read"], is_active=False)

    await run_ensure_admin()

    users = {u.email: u for u in await all_users()}
    assert len(users) == 2
    assert users[other["email"]].is_active is False
    assert users[other["email"]].permissions == ["employees:read"]


async def test_the_admin_is_created_on_every_startup(anonymous_client):
    from app.main import app

    # lifespan_context ejecuta el arranque y el apagado de la app, como uvicorn.
    async with app.router.lifespan_context(app):
        pass
    async with app.router.lifespan_context(app):
        pass

    (admin,) = await all_users()
    assert admin.email == ADMIN_EMAIL
    assert set(admin.permissions) == set(ALL_PERMISSIONS)
