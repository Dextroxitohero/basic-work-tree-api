from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.auth.exceptions import InsufficientPermissionsError, InvalidTokenError
from app.modules.auth.schemas import TokenPayload
from app.modules.auth.verifier import TokenVerifier, get_token_verifier

# Extrae el token de "Authorization: Bearer <token>" y añade el candado en Swagger UI.
# auto_error=False: si falta el header lo gestionamos nosotros, con nuestro ErrorResponse.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> TokenPayload:
    """Autenticación: ¿quién eres?"""
    if credentials is None:
        raise InvalidTokenError()
    return await verifier.verify(credentials.credentials)


def require_permission(permission: str) -> Callable[..., Awaitable[TokenPayload]]:
    """Autorización: ¿puedes hacer esto?

    Es una fábrica: cada llamada devuelve una dependency que exige un permiso concreto.
    """

    async def check(user: Annotated[TokenPayload, Depends(get_current_user)]) -> TokenPayload:
        if permission not in user.permissions:
            raise InsufficientPermissionsError(details={"required": permission})
        return user

    return check
