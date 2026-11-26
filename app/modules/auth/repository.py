from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import (
    Order,
    Page,
    SortSpec,
    apply_page,
    build_page,
    contains_pattern,
    parse_aware_datetime,
)
from app.core.repository import flush
from app.modules.auth.exceptions import UserEmailExistsError
from app.modules.auth.models import User
from app.modules.auth.permissions import ADMIN_PERMISSION

# Constraint de la DB -> error de este módulo.
_CONFLICTS = {"uq_users_email": UserEmailExistsError}

# Número arbitrario que identifica el lock de usuarios en PostgreSQL.
_USERS_LOCK_ID = 7_402

# Columnas por las que se puede ordenar (?sort=).
_SORTS = {
    spec.name: spec
    for spec in (
        SortSpec("email", User.email),
        SortSpec("created_at", User.created_at, parse_aware_datetime),
    )
}


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        return await self._session.scalar(select(User).where(User.email == email))

    async def list_page(
        self,
        *,
        q: str | None,
        is_active: bool | None,
        sort: str,
        order: Order,
        after: str | None,
    ) -> Page[User]:
        stmt = select(User)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        if q is not None:
            pattern = contains_pattern(q)
            stmt = stmt.where(
                User.email.ilike(pattern, escape="\\") | User.full_name.ilike(pattern, escape="\\")
            )
        spec = _SORTS[sort]
        stmt = apply_page(stmt, spec=spec, id_column=User.id, order=order, after=after)
        rows = (await self._session.scalars(stmt)).all()
        return build_page(rows, spec=spec, order=order)

    async def count_other_active_admins(self, user_id: UUID) -> int:
        stmt = select(func.count(User.id)).where(
            User.id != user_id,
            User.is_active,
            User.permissions.contains([ADMIN_PERMISSION]),  # operador @> de arrays
        )
        return await self._session.scalar(stmt) or 0

    async def lock_users(self) -> None:
        """Serializa los cambios de usuarios hasta el final de la transacción.

        Sin esto, dos administradores que se quitan el permiso a la vez pasarían cada uno la
        comprobación "queda otro admin" y juntos dejarían el sistema sin ninguno. También
        evita que dos arranques simultáneos creen el admin sembrado dos veces.
        """
        await self._session.execute(select(func.pg_advisory_xact_lock(_USERS_LOCK_ID)))

    async def save(self, user: User) -> User:
        self._session.add(user)
        await flush(self._session, _CONFLICTS)
        return user
