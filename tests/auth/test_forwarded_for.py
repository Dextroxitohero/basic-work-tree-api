"""El límite de intentos por IP no se puede saltar falsificando X-Forwarded-For."""

import pytest

from app.core.config import get_settings
from app.modules.auth.guard import LOGIN_PER_IP, SIGNUP_PER_IP

REAL_CLIENT = "203.0.113.7"


def login_body(i: int) -> dict:
    # Un email distinto cada vez: solo el límite por IP puede frenar estos intentos.
    return {"email": f"user{i}@example.com", "password": "clave-equivocada-123"}


@pytest.fixture
def behind_one_proxy(monkeypatch):
    """Como en Railway: un proxy de confianza delante de la app."""
    monkeypatch.setattr(get_settings(), "trusted_proxy_hops", 1)


async def test_a_forged_header_does_not_reset_the_login_limit(anonymous_client, behind_one_proxy):
    for i in range(LOGIN_PER_IP[0]):
        # El atacante cambia lo que escribe a la izquierda; el proxy añade su IP real al final.
        headers = {"X-Forwarded-For": f"10.9.{i}.1, {REAL_CLIENT}"}
        response = await anonymous_client.post("/auth/login", json=login_body(i), headers=headers)
        assert response.status_code == 401

    blocked = await anonymous_client.post(
        "/auth/login",
        json=login_body(999),
        headers={"X-Forwarded-For": f"10.9.250.1, {REAL_CLIENT}"},
    )

    assert (blocked.status_code, blocked.json()["error"]) == (429, "too_many_requests")


async def test_another_real_client_is_not_affected(anonymous_client, behind_one_proxy):
    for i in range(LOGIN_PER_IP[0]):
        await anonymous_client.post(
            "/auth/login",
            json=login_body(i),
            headers={"X-Forwarded-For": f"10.9.{i}.1, {REAL_CLIENT}"},
        )

    other = await anonymous_client.post(
        "/auth/login",
        json=login_body(1_000),
        headers={"X-Forwarded-For": "198.51.100.20"},
    )

    assert other.status_code == 401  # su propio cupo, sin bloquear


async def test_a_forged_header_does_not_reset_the_signup_limit(anonymous_client, behind_one_proxy):
    for i in range(SIGNUP_PER_IP[0]):
        response = await anonymous_client.post(
            "/auth/signup",
            json={"full_name": "A", "email": f"nuevo{i}@example.com", "password": "clave-12345"},
            headers={"X-Forwarded-For": f"10.8.{i}.1, {REAL_CLIENT}"},
        )
        assert response.status_code == 201

    blocked = await anonymous_client.post(
        "/auth/signup",
        json={"full_name": "A", "email": "otro@example.com", "password": "clave-12345"},
        headers={"X-Forwarded-For": f"10.8.250.1, {REAL_CLIENT}"},
    )

    assert blocked.status_code == 429


async def test_without_a_trusted_proxy_the_header_is_ignored(anonymous_client):
    # Configuración por defecto (0 proxies): X-Forwarded-For no cuenta para nada.
    assert get_settings().trusted_proxy_hops == 0
    for i in range(LOGIN_PER_IP[0]):
        await anonymous_client.post(
            "/auth/login",
            json=login_body(i),
            headers={"X-Forwarded-For": f"10.7.{i}.1"},
        )

    blocked = await anonymous_client.post(
        "/auth/login",
        json=login_body(999),
        headers={"X-Forwarded-For": "10.7.250.1"},
    )

    assert blocked.status_code == 429
