from collections.abc import Sequence
from typing import Any
from uuid import UUID

from app.modules.job_titles.exceptions import JobTitleNotFoundError
from app.modules.job_titles.models import JobTitle
from app.modules.job_titles.ports import JobTitleStore


class JobTitleService:
    def __init__(self, job_titles: JobTitleStore) -> None:
        self._job_titles = job_titles

    async def list_all(self, *, is_active: bool) -> Sequence[JobTitle]:
        return await self._job_titles.list_all(is_active=is_active)

    async def get(self, job_title_id: UUID) -> JobTitle:
        job_title = await self._job_titles.get_by_id(job_title_id)
        if job_title is None:
            raise JobTitleNotFoundError()
        return job_title

    async def create(self, *, name: str, description: str | None) -> JobTitle:
        return await self._job_titles.save(JobTitle(name=name, description=description))

    async def update(self, job_title_id: UUID, changes: dict[str, Any]) -> JobTitle:
        job_title = await self.get(job_title_id)
        for field, value in changes.items():
            setattr(job_title, field, value)
        return await self._job_titles.save(job_title)
