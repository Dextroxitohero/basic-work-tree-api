"""Registro de modelos: importarlos todos aquí garantiza que Alembic los conozca."""

from app.core.models import Base
from app.modules.departments.models import Department
from app.modules.employees.models import Employee
from app.modules.job_titles.models import JobTitle
from app.modules.positions.models import PositionHistory

__all__ = ["Base", "Department", "Employee", "JobTitle", "PositionHistory"]
