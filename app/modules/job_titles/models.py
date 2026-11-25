from sqlalchemy import String, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, CreatedAtMixin, UpdatedAtMixin, UUIDMixin


class JobTitle(UUIDMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "job_titles"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    # Mapped[str | None] -> columna NULLABLE; Mapped[str] -> NOT NULL.
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(server_default=true())
