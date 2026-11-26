"""Tests unitarios: sin HTTP y sin base de datos, gracias a los puertos (Protocol)."""

from uuid import UUID, uuid4

import pytest

from app.modules.job_titles.exceptions import JobTitleNotFoundError
from app.modules.job_titles.models import JobTitle
from app.modules.job_titles.service import JobTitleService


class InMemoryJobTitles:
    """Cumple el Protocol JobTitleStore sin heredar de él."""

    def __init__(self) -> None:
        self.rows: dict[UUID, JobTitle] = {}

    async def get_by_id(self, job_title_id: UUID) -> JobTitle | None:
        return self.rows.get(job_title_id)

    async def list_all(
        self, *, is_active: bool | None, q: str | None, order: str
    ) -> list[JobTitle]:
        return [row for row in self.rows.values() if is_active in (None, row.is_active)]

    async def save(self, job_title: JobTitle) -> JobTitle:
        job_title.id = job_title.id or uuid4()
        self.rows[job_title.id] = job_title
        return job_title


async def test_update_changes_only_given_fields():
    service = JobTitleService(InMemoryJobTitles())
    title = await service.create(name="Dev", description="original")

    updated = await service.update(title.id, {"name": "Developer"})

    assert (updated.name, updated.description) == ("Developer", "original")


async def test_update_unknown_title():
    service = JobTitleService(InMemoryJobTitles())

    with pytest.raises(JobTitleNotFoundError):
        await service.update(uuid4(), {"name": "x"})
