"""Freno a la fuerza bruta: el limitador y su uso en login y signup."""

import pytest

from app.core.exceptions import TooManyRequestsError
from app.core.rate_limit import SlidingWindowLimiter
from app.modules.auth.guard import (
    LOGIN_FAILURES_PER_EMAIL,
    LOGIN_PER_IP,
    SIGNUP_PER_EMAIL,
    SIGNUP_PER_IP,
)
from tests.conftest import TEST_PASSWORD

# ---------------------------------------------------------------- el limitador (unitario)


class Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_the_limit_then_blocks_with_retry_after():
    clock = Clock()
    limiter = SlidingWindowLimiter(3, 60, clock)

    for _ in range(3):
        limiter.hit("a")
    clock.now += 20

    with pytest.raises(TooManyRequestsError) as error:
        limiter.hit("a")
    assert error.value.retry_after == 40  # el primer evento sale de la ventana en 40 s


def test_window_slides():
    clock = Clock()
    limiter = SlidingWindowLimiter(2, 60, clock)
    limiter.hit("a")
    clock.now += 30
    limiter.hit("a")

    clock.now += 31  # el primero ya salió de la ventana
    limiter.hit("a")

    with pytest.raises(TooManyRequestsError):
        limiter.hit("a")


def test_keys_are_independent_and_reset_works():
    limiter = SlidingWindowLimiter(1, 60, Clock())
    limiter.hit("a")
    limiter.hit("b")

    with pytest.raises(TooManyRequestsError):
        limiter.hit("a")
    limiter.reset("a")
    limiter.hit("a")


def test_check_does_not_count_and_record_does():
    limiter = SlidingWindowLimiter(1, 60, Clock())
    for _ in range(5):
        limiter.check("a")  # solo mira
    limiter.record("a")

    with pytest.raises(TooManyRequestsError):
        limiter.check("a")


def test_a_blocked_hit_is_not_counted():
    clock = Clock()
    limiter = SlidingWindowLimiter(1, 60, clock)
    limiter.hit("a")
    for _ in range(10):
        with pytest.raises(TooManyRequestsError):
            limiter.hit("a")

    clock.now += 61  # solo cuenta el evento aceptado: los rechazados no alargan el bloqueo

    limiter.hit("a")


def test_expired_keys_are_swept_so_memory_does_not_grow():
    clock = Clock()
    limiter = SlidingWindowLimiter(1, 60, clock)
    for i in range(500):
        limiter.hit(f"email-{i}")
    clock.now += 61

    for _ in range(1_000):  # fuerza el barrido periódico
        limiter.check("otra")

    assert limiter._events == {}


# ---------------------------------------------------------------- login


def login_body(email, password="clave-equivocada-123"):
    return {"email": email, "password": password}


async def test_login_is_blocked_after_too_many_failures_for_an_email(anonymous_client, make_user):
    await make_user(email="luis@example.com")
    max_failures = LOGIN_FAILURES_PER_EMAIL[0]

    for _ in range(max_failures):
        response = await anonymous_client.post("/auth/login", json=login_body("luis@example.com"))
        assert response.status_code == 401
    # Bloqueada: incluso la contraseña CORRECTA recibe 429 hasta que pase la ventana.
    blocked = await anonymous_client.post(
        "/auth/login", json=login_body("luis@example.com", TEST_PASSWORD)
    )

    assert (blocked.status_code, blocked.json()["error"]) == (429, "too_many_requests")
    assert int(blocked.headers["Retry-After"]) > 0


async def test_failures_are_counted_per_email_and_case_insensitively(anonymous_client, make_user):
    await make_user(email="luis@example.com")
    await make_user(email="ana@example.com")

    for i in range(LOGIN_FAILURES_PER_EMAIL[0]):
        email = "LUIS@example.com" if i % 2 else "luis@example.com"
        await anonymous_client.post("/auth/login", json=login_body(email))

    luis = await anonymous_client.post(
        "/auth/login", json=login_body("luis@example.com", TEST_PASSWORD)
    )
    ana = await anonymous_client.post(
        "/auth/login", json=login_body("ana@example.com", TEST_PASSWORD)
    )

    assert luis.status_code == 429
    assert ana.status_code == 200


async def test_failures_of_unknown_emails_are_limited_too(anonymous_client):
    for _ in range(LOGIN_FAILURES_PER_EMAIL[0]):
        await anonymous_client.post("/auth/login", json=login_body("nadie@example.com"))

    response = await anonymous_client.post("/auth/login", json=login_body("nadie@example.com"))

    # Mismo comportamiento que con un email real: no se puede distinguir si existe.
    assert response.status_code == 429


async def test_a_successful_login_resets_the_failure_counter(anonymous_client, make_user):
    await make_user(email="luis@example.com")
    almost = LOGIN_FAILURES_PER_EMAIL[0] - 1

    for _ in range(almost):
        await anonymous_client.post("/auth/login", json=login_body("luis@example.com"))
    ok = await anonymous_client.post(
        "/auth/login", json=login_body("luis@example.com", TEST_PASSWORD)
    )
    for _ in range(almost):
        await anonymous_client.post("/auth/login", json=login_body("luis@example.com"))
    still_ok = await anonymous_client.post(
        "/auth/login", json=login_body("luis@example.com", TEST_PASSWORD)
    )

    assert ok.status_code == 200
    assert still_ok.status_code == 200


async def test_login_is_limited_per_ip_whatever_the_email(anonymous_client):
    limit = LOGIN_PER_IP[0]

    for i in range(limit):
        response = await anonymous_client.post(
            "/auth/login", json=login_body(f"user{i}@example.com")
        )
        assert response.status_code == 401
    blocked = await anonymous_client.post("/auth/login", json=login_body("otro@example.com"))

    assert (blocked.status_code, blocked.json()["error"]) == (429, "too_many_requests")
    assert "Retry-After" in blocked.headers


# ---------------------------------------------------------------- signup


async def test_signup_is_limited_per_ip(anonymous_client):
    limit = SIGNUP_PER_IP[0]

    for i in range(limit):
        response = await anonymous_client.post(
            "/auth/signup",
            json={"full_name": "A", "email": f"user{i}@example.com", "password": "clave-12345"},
        )
        assert response.status_code == 201
    blocked = await anonymous_client.post(
        "/auth/signup",
        json={"full_name": "A", "email": "otro@example.com", "password": "clave-12345"},
    )

    assert (blocked.status_code, blocked.json()["error"]) == (429, "too_many_requests")


async def test_signup_is_limited_per_email(anonymous_client):
    body = {"full_name": "A", "email": "repetido@example.com", "password": "clave-12345"}
    limit = SIGNUP_PER_EMAIL[0]

    first = await anonymous_client.post("/auth/signup", json=body)
    for _ in range(limit - 1):
        assert (await anonymous_client.post("/auth/signup", json=body)).status_code == 409
    blocked = await anonymous_client.post("/auth/signup", json=body)

    assert first.status_code == 201
    assert blocked.status_code == 429
