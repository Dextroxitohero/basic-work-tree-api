"""Puertos: lo que el servicio necesita de fuera, sin saber quién lo implementa."""

from typing import Protocol
from uuid import UUID

from app.core.pagination import Order, Page
from app.modules.auth.models import User


class UserStore(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
    async def list_page(
        self,
        *,
        q: str | None,
        is_active: bool | None,
        sort: str,
        order: Order,
        after: str | None,
    ) -> Page[User]: ...
    async def count_other_active_admins(self, user_id: UUID) -> int: ...
    async def lock_users(self) -> None: ...
    async def save(self, user: User) -> User: ...


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...

    async def verify(self, password: str, password_hash: str | None) -> bool:
        """Con password_hash=None (el email no existe) tarda lo mismo y devuelve False."""
        ...


class TokenIssuer(Protocol):
    def issue(self, user: User) -> tuple[str, int]:
        """Devuelve el token de acceso y los segundos que dura."""
        ...
