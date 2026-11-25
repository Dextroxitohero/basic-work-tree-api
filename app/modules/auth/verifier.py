from functools import lru_cache
from typing import Protocol

from jwt import PyJWKClient

from app.core.config import get_settings
from app.modules.auth.auth0 import Auth0TokenVerifier
from app.modules.auth.local import LocalTokenVerifier
from app.modules.auth.schemas import TokenPayload


class TokenVerifier(Protocol):
    """Contrato para validar tokens. Agregar un proveedor = otra clase con verify()."""

    async def verify(self, token: str) -> TokenPayload: ...


@lru_cache
def get_token_verifier() -> TokenVerifier:
    """Elige el verificador según AUTH_MODE. El resto de la app no sabe cuál se usa."""
    settings = get_settings()
    if settings.auth_mode == "local":
        return LocalTokenVerifier(
            settings.local_jwt_secret.get_secret_value(), audience=settings.auth0_audience
        )
    issuer = f"https://{settings.auth0_domain}/"
    # PyJWKClient guarda en caché las claves públicas y las vuelve a pedir si Auth0 las rota.
    return Auth0TokenVerifier(
        PyJWKClient(f"{issuer}.well-known/jwks.json"),
        audience=settings.auth0_audience,
        issuer=issuer,
    )
