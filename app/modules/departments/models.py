from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, CreatedAtMixin, UUIDMixin


class Department(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    # employees y departments se referencian mutuamente. use_alter crea esta FK con un
    # ALTER TABLE posterior, cuando ya existen ambas tablas.
    manager_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", use_alter=True), index=True
    )

    # Índice (columna, id) para ordenar y paginar por cursor. El nombre ya tiene su propio
    # índice único, así que solo hace falta el de created_at.
    __table_args__ = (Index("ix_departments_created_at_id", "created_at", "id"),)

    # employee_count NO es una columna: el repositorio lo calcula en cada consulta y lo deja
    # como atributo del objeto (ver DepartmentRepository).
