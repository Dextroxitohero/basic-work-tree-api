from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import Base, CreatedAtMixin, UUIDMixin

if TYPE_CHECKING:
    from app.modules.job_titles.models import JobTitle


class PositionHistory(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "position_history"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"))
    job_title_id: Mapped[UUID] = mapped_column(ForeignKey("job_titles.id"), index=True)
    salary: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    start_date: Mapped[date]
    end_date: Mapped[date | None]  # NULL = puesto actual
    notes: Mapped[str | None] = mapped_column(Text)

    job_title: Mapped["JobTitle"] = relationship(viewonly=True, lazy="raise")

    # La DB es la última línea de defensa: protege las reglas incluso con requests simultáneos.
    __table_args__ = (
        CheckConstraint("salary > 0", name="salary_positive"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="valid_dates"),
        UniqueConstraint("employee_id", "start_date"),
        # Índice único PARCIAL: como mucho una fila con end_date NULL por empleado.
        Index(
            "uq_position_history_active",
            "employee_id",
            unique=True,
            postgresql_where=text("end_date IS NULL"),
        ),
    )
