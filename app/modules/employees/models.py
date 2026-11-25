from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base, CreatedAtMixin, UpdatedAtMixin, UUIDMixin

if TYPE_CHECKING:
    from app.modules.positions.models import PositionHistory


class Employee(UUIDMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "employees"

    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    hire_date: Mapped[date]
    is_active: Mapped[bool] = mapped_column(server_default=true())
    # Auto-referencia: el jefe es otro empleado. Así se forma el árbol.
    manager_id: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id"), index=True)
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id"), index=True)

    # Las relaciones son viewonly (solo lectura): las escrituras pasan siempre por las columnas
    # *_id y los repositorios, así hay una sola forma de modificar los datos.
    current_position: Mapped["PositionHistory | None"] = relationship(
        primaryjoin=(
            "and_(Employee.id == PositionHistory.employee_id, PositionHistory.end_date.is_(None))"
        ),
        uselist=False,
        viewonly=True,
        lazy="raise",
    )
    position_history: Mapped[list["PositionHistory"]] = relationship(
        order_by="PositionHistory.start_date.desc()",
        viewonly=True,
        lazy="raise",
    )
    direct_reports: Mapped[list["Employee"]] = relationship(
        # remote() marca qué lado del JOIN es "el otro" empleado (el subordinado).
        primaryjoin=(
            "and_(Employee.id == remote(foreign(Employee.manager_id)), remote(Employee.is_active))"
        ),
        order_by="Employee.last_name, Employee.first_name",
        viewonly=True,
        lazy="raise",
    )
