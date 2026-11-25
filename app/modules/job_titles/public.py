"""Lo que otros módulos pueden usar de job_titles."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_titles.exceptions import JobTitleInactiveError, JobTitleNotFoundError
from app.modules.job_titles.ports import JobTitleStore
from app.modules.job_titles.repository import JobTitleRepository


class JobTitleCatalog:
    def __init__(self, job_titles: JobTitleStore) -> None:
        self._job_titles = job_titles

    async def ensure_assignable(self, job_title_id: UUID) -> None:
        job_title = await self._job_titles.get_by_id(job_title_id)
        if job_title is None:
            raise JobTitleNotFoundError()
        if not job_title.is_active:
            raise JobTitleInactiveError()


def get_job_title_catalog(session: AsyncSession) -> JobTitleCatalog:
    return JobTitleCatalog(JobTitleRepository(session))
