"""Lo que otros módulos pueden usar de employees."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.employees.directory import EmployeeDirectory
from app.modules.employees.repository import EmployeeRepository

__all__ = ["EmployeeDirectory", "get_employee_directory"]


def get_employee_directory(session: AsyncSession) -> EmployeeDirectory:
    return EmployeeDirectory(EmployeeRepository(session))
