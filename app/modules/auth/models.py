from sqlalchemy import CheckConstraint, String, Text, text, true
from sqlalchemy.dialects.postgresql import ARRAY  # el ARRAY de PostgreSQL trae el operador @>
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, CreatedAtMixin, UpdatedAtMixin, UUIDMixin


class User(UUIDMixin, CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str | None] = mapped_column(String(120))
    # Hash Argon2id (incluye su sal y parámetros). La contraseña jamás se guarda.
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(server_default=true())
    permissions: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{employees:read}'")
    )

    # La DB es la última línea de defensa: el UNIQUE solo compara textos idénticos, así que
    # Ana@x.com y ana@x.com serían dos usuarios si se pudiera guardar en mayúsculas.
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)
