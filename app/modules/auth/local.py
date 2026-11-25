"""Autenticación local, SOLO para desarrollo: permite usar la API sin una cuenta de Auth0."""

from datetime import UTC, datetime, timedelta

import jwt

from app.modules.auth.exceptions import InvalidTokenError
from app.modules.auth.schemas import TokenPayload

LOCAL_ISSUER = "local-dev"

ADMIN = TokenPayload(
    sub="local|admin",
    email="admin@example.com",
    permissions=[
        "employees:read",
        "employees:write",
        "positions:write",
        "job-titles:write",
        "departments:write",
    ],
)


class LocalTokenVerifier:
    """Cumple el Protocol TokenVerifier, igual que Auth0TokenVerifier.

    HS256 es simétrico: el mismo secreto firma y verifica. Auth0 usa RS256 (asimétrico),
    donde la API solo tiene la clave pública y no puede fabricar tokens.
    """

    def __init__(self, secret: str, *, audience: str) -> None:
        self._secret = secret
        self._audience = audience

    async def verify(self, token: str) -> TokenPayload:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience=self._audience,
                issuer=LOCAL_ISSUER,
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError() from exc
        return TokenPayload(
            sub=claims["sub"],
            email=claims.get("email"),
            permissions=claims.get("permissions", []),
        )


def create_token(
    user: TokenPayload, secret: str, *, audience: str, lifetime: timedelta = timedelta(hours=12)
) -> str:
    claims = user.model_dump() | {
        "iss": LOCAL_ISSUER,
        "aud": audience,
        "exp": datetime.now(UTC) + lifetime,
    }
    return jwt.encode(claims, secret, algorithm="HS256")
