from typing import Annotated

from fastapi import Depends

from app.core.database import DbSession
from app.modules.departments.repository import DepartmentRepository
from app.modules.departments.service import DepartmentService
from app.modules.employees.public import get_employee_directory


def get_department_service(db: DbSession) -> DepartmentService:
    return DepartmentService(DepartmentRepository(db), get_employee_directory(db))


DepartmentServiceDep = Annotated[DepartmentService, Depends(get_department_service)]
