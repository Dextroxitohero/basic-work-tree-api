"""GET /users y PATCH /users/{id}: gestión de permisos y de cuentas."""

from uuid import uuid4

import pytest

from app.core import pagination
from app.modules.auth.permissions import ALL_PERMISSIONS


@pytest.fixture
def small_pages(monkeypatch):
    monkeypatch.setattr(pagination, "PAGE_SIZE", 3)


# ---------------------------------------------------------------- listado


async def test_list_users_shows_everyone_with_the_auth_user_shape(client, admin, make_user):
    reader = await make_user(permissions=["employees:read"], is_active=False)

    page = (await client.get("/users")).json()

    assert page["next_cursor"] is None
    assert {u["id"] for u in page["items"]} == {admin["id"], reader["id"]}
    assert set(page["items"][0]) == {"id", "email", "full_name", "is_active", "permissions"}
    assert "password_hash" not in str(page)


async def test_list_users_paginates_sorts_and_filters(client, make_user, get_all, small_pages):
    for i in range(6):
        await make_user(email=f"u{i}@corp.com", is_active=i % 2 == 0)

    everyone = await get_all("/users")
    by_email_desc = await get_all("/users", sort="email", order="desc")
    only_active = await get_all("/users", is_active=True)
    only_inactive = await get_all("/users", is_active=False)
    searched = await get_all("/users", q="CORP.com")

    assert len(everyone) == 7  # 6 + el admin del cliente
    assert [u["email"] for u in everyone] == sorted(u["email"] for u in everyone)
    assert [u["email"] for u in by_email_desc] == sorted(
        (u["email"] for u in by_email_desc), reverse=True
    )
    assert len(only_active) == 4 and all(u["is_active"] for u in only_active)
    assert len(only_inactive) == 3 and not any(u["is_active"] for u in only_inactive)
    assert len(searched) == 6


async def test_list_users_search_matches_name_and_email(client, make_user):
    await make_user(email="zoe@example.com")

    by_email = (await client.get("/users", params={"q": "ZOE"})).json()["items"]
    by_name = (await client.get("/users", params={"q": "usuario 1"})).json()["items"]

    assert [u["email"] for u in by_email] == ["zoe@example.com"]
    assert len(by_name) >= 1


@pytest.mark.parametrize(
    "params", [{"sort": "password_hash"}, {"order": "x"}, {"after": "basura"}, {"q": ""}]
)
async def test_list_users_invalid_query_is_422(client, params):
    response = await client.get("/users", params=params)

    assert (response.status_code, response.json()["error"]) == (422, "validation_error")


# ---------------------------------------------------------------- cambios


async def test_admin_can_raise_permissions_after_signup(client, anonymous_client):
    created = await anonymous_client.post(
        "/auth/signup",
        json={"full_name": "Ana", "email": "ana@example.com", "password": "una-clave-segura"},
    )
    user_id = created.json()["user"]["id"]
    assert created.json()["user"]["permissions"] == ["employees:read"]

    response = await client.patch(
        f"/users/{user_id}",
        json={"permissions": ["job-titles:write", "employees:read", "job-titles:write"]},
    )

    assert response.status_code == 200
    # Sin duplicados y en orden.
    assert response.json()["permissions"] == ["employees:read", "job-titles:write"]
    assert response.json()["email"] == "ana@example.com"


async def test_admin_can_deactivate_and_reactivate(client, make_user):
    user = await make_user()

    off = await client.patch(f"/users/{user['id']}", json={"is_active": False})
    on = await client.patch(f"/users/{user['id']}", json={"is_active": True})

    assert off.json()["is_active"] is False
    assert on.json()["is_active"] is True


async def test_patch_changes_only_the_given_fields(client, make_user):
    user = await make_user(permissions=["employees:read", "employees:write"])

    response = await client.patch(f"/users/{user['id']}", json={"is_active": False})

    assert response.json()["permissions"] == ["employees:read", "employees:write"]


async def test_patch_can_clear_all_permissions(client, make_user):
    user = await make_user()

    response = await client.patch(f"/users/{user['id']}", json={"permissions": []})

    assert response.json()["permissions"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"permissions": ["superuser"]},
        {"permissions": "employees:read"},
        {"permissions": None},
        {"is_active": None},
        {"email": "otro@example.com"},
        {"password_hash": "x"},
        {"full_name": "x"},
    ],
)
async def test_patch_validation(client, make_user, body):
    user = await make_user()

    response = await client.patch(f"/users/{user['id']}", json=body)

    assert (response.status_code, response.json()["error"]) == (422, "validation_error")


async def test_patch_unknown_user_is_404(client):
    response = await client.patch(f"/users/{uuid4()}", json={"is_active": False})

    assert (response.status_code, response.json()["error"]) == (404, "user_not_found")


# ---------------------------------------------------------------- A13: siempre un admin


async def test_the_last_admin_cannot_be_deactivated(client, admin):
    response = await client.patch(f"/users/{admin['id']}", json={"is_active": False})

    assert (response.status_code, response.json()["error"]) == (409, "last_admin_required")
    assert (await client.get("/auth/me")).json()["is_active"] is True


async def test_the_last_admin_cannot_lose_the_users_permission(client, admin):
    without = [p for p in ALL_PERMISSIONS if p != "users:write"]

    response = await client.patch(f"/users/{admin['id']}", json={"permissions": without})
    cleared = await client.patch(f"/users/{admin['id']}", json={"permissions": []})

    for r in (response, cleared):
        assert (r.status_code, r.json()["error"]) == (409, "last_admin_required")


async def test_the_last_admin_can_change_other_permissions(client, admin):
    response = await client.patch(
        f"/users/{admin['id']}", json={"permissions": ["users:write", "employees:read"]}
    )

    assert response.status_code == 200


async def test_an_admin_can_step_down_when_another_active_admin_exists(
    client, anonymous_client, admin, make_user
):
    other = await make_user(permissions=["users:write"])

    first = await client.patch(f"/users/{admin['id']}", json={"permissions": []})
    # Ahora el único admin es "other": ya no puede quitarse el permiso ni desactivarse.
    second = await anonymous_client.patch(
        f"/users/{other['id']}", json={"is_active": False}, headers=other["headers"]
    )
    third = await anonymous_client.patch(
        f"/users/{other['id']}", json={"permissions": []}, headers=other["headers"]
    )

    assert first.status_code == 200
    for r in (second, third):
        assert (r.status_code, r.json()["error"]) == (409, "last_admin_required")


async def test_an_inactive_user_with_the_permission_is_not_an_admin(client, admin, make_user):
    await make_user(permissions=["users:write"], is_active=False)

    # El otro está desactivado: no cuenta, así que "admin" sigue siendo el último.
    response = await client.patch(f"/users/{admin['id']}", json={"is_active": False})

    assert (response.status_code, response.json()["error"]) == (409, "last_admin_required")


async def test_deactivating_a_non_admin_is_always_allowed(client, make_user):
    user = await make_user(permissions=["employees:read"])

    response = await client.patch(f"/users/{user['id']}", json={"is_active": False})

    assert response.status_code == 200
