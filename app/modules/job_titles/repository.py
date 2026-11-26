from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Order, contains_pattern
from app.core.repository import flush
from app.modules.job_titles.exceptions import JobTitleNameExistsError
from app.modules.job_titles.models import JobTitle

# Constraint de la DB -> error de este módulo.
_CONFLICTS = {"uq_job_titles_name": JobTitleNameExistsError}


class JobTitleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, job_title_id: UUID) -> JobTitle | None:
        return await self._session.get(JobTitle, job_title_id)

    async def list_all(
        self, *, is_active: bool | None, q: str | None, order: Order
    ) -> Sequence[JobTitle]:
        stmt = select(JobTitle)
        if is_active is not None:
            stmt = stmt.where(JobTitle.is_active == is_active)
        if q is not None:
            stmt = stmt.where(JobTitle.name.ilike(contains_pattern(q), escape="\\"))
        # El catálogo es pequeño: se devuelve completo, sin paginar. Solo se ordena por name.
        direction = asc if order == "asc" else desc
        return (await self._session.scalars(stmt.order_by(direction(JobTitle.name)))).all()

    async def save(self, job_title: JobTitle) -> JobTitle:
        self._session.add(job_title)
        await flush(self._session, _CONFLICTS)
        return job_title
