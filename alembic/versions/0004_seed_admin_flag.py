"""marca de administrador sembrado"""

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_seed_admin", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    # Hasta ahora la única forma de tener users:write era el administrador sembrado, así que
    # los administradores que ya existen se marcan para que ensure_admin siga restaurándolos.
    op.execute("UPDATE users SET is_seed_admin = true WHERE 'users:write' = ANY(permissions)")


def downgrade() -> None:
    op.drop_column("users", "is_seed_admin")
