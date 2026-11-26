"""indices para ordenar y paginar por cursor"""

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None

# (tabla, nombre del índice, columnas). Cada par (columna de orden, id) sirve al ORDER BY
# y a la comparación de filas del cursor: WHERE (columna, id) > (:valor, :id).
_INDEXES = [
    ("employees", "ix_employees_last_name_id", ["last_name", "id"]),
    ("employees", "ix_employees_first_name_id", ["first_name", "id"]),
    ("employees", "ix_employees_hire_date_id", ["hire_date", "id"]),
    ("employees", "ix_employees_created_at_id", ["created_at", "id"]),
    ("departments", "ix_departments_created_at_id", ["created_at", "id"]),
]


def upgrade() -> None:
    for table, name, columns in _INDEXES:
        op.create_index(op.f(name), table, columns)


def downgrade() -> None:
    for table, name, _ in reversed(_INDEXES):
        op.drop_index(op.f(name), table_name=table)
