from typing import Annotated

from fastapi import Depends

from app.core.database import DbSession
from app.modules.departments.public import get_department_directory
from app.modules.employees.directory import EmployeeDirectory
from app.modules.employees.repository import EmployeeRepository
from app.modules.employees.service import EmployeeService
from app.modules.positions.public import get_position_closer


def get_employee_service(db: DbSession) -> EmployeeService:
    employees = EmployeeRepository(db)
    # Aquí se "enchufan" los puertos: el servicio no sabe de qué módulo viene cada pieza.
    return EmployeeService(
        employees,
        EmployeeDirectory(employees),
        get_position_closer(db),
        get_department_directory(db),
    )


EmployeeServiceDep = Annotated[EmployeeService, Depends(get_employee_service)]
