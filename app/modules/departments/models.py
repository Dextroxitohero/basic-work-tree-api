from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base, CreatedAtMixin, UUIDMixin

# SQLAlchemy resuelve "Employee" por su registro interno en runtime, así que este import
# solo lo necesita el editor / type checker. Evita el import circular.
if TYPE_CHECKING:
    from app.modules.employees.models import Employee


class Department(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    # employees y departments se referencian mutuamente. use_alter crea esta FK con un
    # ALTER TABLE posterior, cuando ya existen ambas tablas.
    manager_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", use_alter=True), index=True
    )

    # lazy="raise": si alguien olvida cargar la relación, falla con un error claro en lugar
    # de lanzar un query oculto (problema N+1, y además no permitido en async).
    employees: Mapped[list["Employee"]] = relationship(
        primaryjoin="and_(Department.id == foreign(Employee.department_id), Employee.is_active)",
        order_by="Employee.last_name, Employee.first_name",
        viewonly=True,
        lazy="raise",
    )
