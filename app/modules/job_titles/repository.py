from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def list_all(self, *, is_active: bool) -> Sequence[JobTitle]:
        stmt = select(JobTitle).where(JobTitle.is_active == is_active).order_by(JobTitle.name)
        return (await self._session.scalars(stmt)).all()

    async def save(self, job_title: JobTitle) -> JobTitle:
        self._session.add(job_title)
        await flush(self._session, _CONFLICTS)
        return job_title
