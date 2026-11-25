from typing import Annotated

from fastapi import Depends

from app.core.database import DbSession
from app.modules.employees.public import get_employee_directory
from app.modules.job_titles.public import get_job_title_catalog
from app.modules.positions.repository import PositionRepository
from app.modules.positions.service import PositionService


def get_position_service(db: DbSession) -> PositionService:
    # Aquí se "enchufan" los puertos: el servicio no sabe de qué módulo viene cada pieza.
    return PositionService(
        PositionRepository(db), get_employee_directory(db), get_job_title_catalog(db)
    )


PositionServiceDep = Annotated[PositionService, Depends(get_position_service)]
