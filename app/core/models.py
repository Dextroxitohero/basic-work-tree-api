from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nombres predecibles para los constraints. Sin esto PostgreSQL los inventa, y no podríamos
# saber de forma fiable qué constraint se violó (ver core/repository.py).
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Trae los valores generados por la DB (id, created_at, updated_at) en el mismo
    # INSERT/UPDATE. Sin esto, leerlos dispararía un query implícito, que en async falla.
    __mapper_args__ = {"eager_defaults": True}


# Los mixins evitan repetir las mismas columnas en cada modelo.
class UUIDMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UpdatedAtMixin:
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
