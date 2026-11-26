from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.database import DbSession
from app.modules.auth.exceptions import InsufficientPermissionsError, InvalidTokenError
from app.modules.auth.guard import AuthGuard, get_auth_guard
from app.modules.auth.models import User
from app.modules.auth.passwords import Argon2PasswordHasher
from app.modules.auth.repository import UserRepository
from app.modules.auth.service import AuthService
from app.modules.auth.tokens import JwtTokens, get_tokens

# Extrae el token de "Authorization: Bearer <token>" y añade el candado en Swagger UI.
# auto_error=False: si falta el header lo gestionamos nosotros, con nuestro ErrorResponse.
bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_password_hasher() -> Argon2PasswordHasher:
    # Una sola instancia por proceso: calcula su hash falso al crearse y no hace falta repetirlo.
    return Argon2PasswordHasher()


def get_auth_service(db: DbSession) -> AuthService:
    return AuthService(
        UserRepository(db),
        get_password_hasher(),
        get_tokens(),
        # Nadie puede registrarse con el email del administrador sembrado.
        reserved_emails=frozenset({get_settings().admin_email}),
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
AuthGuardDep = Annotated[AuthGuard, Depends(get_auth_guard)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    tokens: Annotated[JwtTokens, Depends(get_tokens)],
    service: AuthServiceDep,
) -> User:
    """Autenticación: ¿quién eres? El usuario se carga de la base en cada petición."""
    if credentials is None:
        raise InvalidTokenError()
    payload = tokens.verify(credentials.credentials)
    return await service.authenticate(payload.sub)


def require_permission(permission: str) -> Callable[..., Awaitable[User]]:
    """Autorización: ¿puedes hacer esto?

    Es una fábrica: cada llamada devuelve una dependency que exige un permiso concreto.
    Los permisos son los de la base de datos, así un cambio surte efecto al instante.
    """

    async def check(user: Annotated[User, Depends(get_current_user)]) -> User:
        if permission not in user.permissions:
            raise InsufficientPermissionsError(details={"required": permission})
        return user

    return check
