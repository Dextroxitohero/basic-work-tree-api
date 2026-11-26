from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.pagination import Order, Page
from app.modules.auth.exceptions import (
    AccountDisabledError,
    InvalidCredentialsError,
    InvalidTokenError,
    LastAdminError,
    UserNotFoundError,
)
from app.modules.auth.models import User
from app.modules.auth.permissions import ADMIN_PERMISSION, ALL_PERMISSIONS, DEFAULT_PERMISSIONS
from app.modules.auth.ports import PasswordHasher, TokenIssuer, UserStore


@dataclass
class Session:
    """Lo que devuelven el signup y el login: el usuario y su token de acceso."""

    user: User
    access_token: str
    expires_in: int


def _is_admin(permissions: list[str], is_active: bool) -> bool:
    return is_active and ADMIN_PERMISSION in permissions


class AuthService:
    """Reglas de negocio de usuarios y sesiones. No conoce HTTP ni SQL."""

    def __init__(self, users: UserStore, hasher: PasswordHasher, tokens: TokenIssuer) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens

    async def signup(self, *, full_name: str, email: str, password: str) -> Session:
        # Los permisos no son un parámetro: quien se registra solo siempre recibe lectura.
        user = await self._users.save(
            User(
                email=email.lower(),
                full_name=full_name,
                password_hash=await self._hasher.hash(password),
                is_active=True,
                permissions=list(DEFAULT_PERMISSIONS),
            )
        )
        return self._session(user)

    async def login(self, *, email: str, password: str) -> Session:
        user = await self._users.get_by_email(email.lower())
        # Se verifica SIEMPRE, aunque el email no exista (contra un hash falso): así el tiempo
        # de respuesta no delata qué emails están registrados.
        valid = await self._hasher.verify(password, user.password_hash if user else None)
        if user is None or not valid:
            raise InvalidCredentialsError()
        # La cuenta desactivada solo se revela a quien conoce la contraseña.
        if not user.is_active:
            raise AccountDisabledError()
        return self._session(user)

    async def authenticate(self, user_id: UUID) -> User:
        """El usuario de un token válido. Los permisos son los de la base, no los del token."""
        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            # Aunque el token no haya caducado, un usuario borrado o desactivado no entra.
            raise InvalidTokenError()
        return user

    async def list_page(
        self, *, q: str | None, is_active: bool | None, sort: str, order: Order, after: str | None
    ) -> Page[User]:
        return await self._users.list_page(
            q=q, is_active=is_active, sort=sort, order=order, after=after
        )

    async def update_user(self, user_id: UUID, changes: dict[str, Any]) -> User:
        """changes contiene SOLO los campos que envió el cliente."""
        # El lock va ANTES de leer, para que dos cambios simultáneos no se pisen al contar
        # los administradores. Se libera solo al terminar la transacción.
        await self._users.lock_users()
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()

        permissions = changes.get("permissions", user.permissions)
        is_active = changes.get("is_active", user.is_active)
        loses_admin = _is_admin(user.permissions, user.is_active) and not _is_admin(
            permissions, is_active
        )
        if loses_admin and await self._users.count_other_active_admins(user.id) == 0:
            raise LastAdminError()

        for name, value in changes.items():
            setattr(user, name, value)
        return await self._users.save(user)

    async def ensure_admin(self, *, email: str, password: str) -> None:
        """Crea el administrador si no existe; si existe, lo restaura. Es idempotente.

        Restaurar significa volver a activarlo y darle todos los permisos. La contraseña de
        un admin existente nunca se toca: es la que él eligió.
        """
        await self._users.lock_users()  # dos arranques simultáneos no lo crean dos veces
        user = await self._users.get_by_email(email.lower())
        if user is None:
            await self._users.save(
                User(
                    email=email.lower(),
                    full_name="Administrador",
                    password_hash=await self._hasher.hash(password),
                    is_active=True,
                    permissions=list(ALL_PERMISSIONS),
                )
            )
            return
        if not user.is_active or set(user.permissions) != set(ALL_PERMISSIONS):
            user.is_active = True
            user.permissions = list(ALL_PERMISSIONS)
            await self._users.save(user)

    def _session(self, user: User) -> Session:
        access_token, expires_in = self._tokens.issue(user)
        return Session(user=user, access_token=access_token, expires_in=expires_in)
