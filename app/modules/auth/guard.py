"""Freno a la fuerza bruta en login y signup (por IP y por email)."""

from functools import lru_cache

from app.core.rate_limit import SlidingWindowLimiter

MINUTE = 60
HOUR = 3_600

# Intentos de login por IP. Es generoso: detrás de una oficina o de un NAT comparten IP.
LOGIN_PER_IP = (30, MINUTE)
# Fallos de login por email. Al llegar al máximo, esa cuenta queda bloqueada un rato, incluso
# con la contraseña correcta; así adivinar contraseñas deja de ser viable.
LOGIN_FAILURES_PER_EMAIL = (5, 15 * MINUTE)
SIGNUP_PER_IP = (10, HOUR)
SIGNUP_PER_EMAIL = (3, HOUR)


class AuthGuard:
    def __init__(self) -> None:
        self._login_ip = SlidingWindowLimiter(*LOGIN_PER_IP)
        self._login_failures = SlidingWindowLimiter(*LOGIN_FAILURES_PER_EMAIL)
        self._signup_ip = SlidingWindowLimiter(*SIGNUP_PER_IP)
        self._signup_email = SlidingWindowLimiter(*SIGNUP_PER_EMAIL)

    def before_login(self, *, ip: str, email: str) -> None:
        self._login_ip.hit(ip)
        self._login_failures.check(email)

    def login_failed(self, email: str) -> None:
        self._login_failures.record(email)

    def login_succeeded(self, email: str) -> None:
        self._login_failures.reset(email)

    def before_signup(self, *, ip: str, email: str) -> None:
        self._signup_ip.hit(ip)
        self._signup_email.hit(email)

    def clear(self) -> None:
        for limiter in (
            self._login_ip,
            self._login_failures,
            self._signup_ip,
            self._signup_email,
        ):
            limiter.clear()


@lru_cache
def get_auth_guard() -> AuthGuard:
    # Un solo guardia por proceso: los contadores deben compartirse entre requests.
    return AuthGuard()
