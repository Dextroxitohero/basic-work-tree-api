"""JWT emitidos y verificados por la propia API. Es el único verificador."""

from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from pydantic import ValidationError

from app.core.config import get_settings
from app.modules.auth.exceptions import InvalidTokenError
from app.modules.auth.models import User
from app.modules.auth.schemas import TokenPayload

ISSUER = "employee-work-tree-api"
AUDIENCE = "employee-work-tree-api"
LIFETIME = timedelta(hours=12)


class JwtTokens:
    """Cumple el Protocol TokenIssuer y además verifica.

    HS256 es simétrico: el mismo secreto firma y verifica. Sirve porque emisor y verificador
    son la misma aplicación; quien conozca JWT_SECRET puede fabricar tokens de admin.
    """

    def __init__(self, secret: str, *, lifetime: timedelta = LIFETIME) -> None:
        self._secret = secret
        self._lifetime = lifetime

    def issue(self, user: User) -> tuple[str, int]:
        now = datetime.now(UTC)
        claims = {
            "sub": str(user.id),
            "email": user.email,
            "permissions": list(user.permissions),
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + self._lifetime,
        }
        return jwt.encode(claims, self._secret, algorithm="HS256"), int(
            self._lifetime.total_seconds()
        )

    def verify(self, token: str) -> TokenPayload:
        """Comprueba firma, caducidad, audiencia y emisor. No consulta la base de datos."""
        try:
            # Fijar algorithms es obligatorio: nunca se debe confiar en el algoritmo que
            # declara el propio token (el ataque "alg: none").
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience=AUDIENCE,
                issuer=ISSUER,
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
            return TokenPayload(
                sub=claims["sub"],
                email=claims.get("email"),
                permissions=claims.get("permissions", []),
            )
        except (jwt.PyJWTError, ValidationError) as exc:  # ValidationError: sub no es un UUID
            raise InvalidTokenError() from exc


@lru_cache
def get_tokens() -> JwtTokens:
    return JwtTokens(get_settings().jwt_secret.get_secret_value())
