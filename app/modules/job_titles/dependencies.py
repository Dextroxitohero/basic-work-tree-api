from typing import Annotated

from fastapi import Depends

from app.core.database import DbSession
from app.modules.job_titles.repository import JobTitleRepository
from app.modules.job_titles.service import JobTitleService


def get_job_title_service(db: DbSession) -> JobTitleService:
    return JobTitleService(JobTitleRepository(db))


# Alias con Annotated: el router escribe "service: JobTitleServiceDep" y listo.
JobTitleServiceDep = Annotated[JobTitleService, Depends(get_job_title_service)]
