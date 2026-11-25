"""initial schema"""

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _timestamp(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


# op.f() indica que el nombre ya es definitivo y no debe pasar por la convención de nombres.
def upgrade() -> None:
    op.create_table(
        "job_titles",
        _id(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_titles")),
        sa.UniqueConstraint("name", name=op.f("uq_job_titles_name")),
    )
    op.create_table(
        "departments",
        _id(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("manager_id", sa.Uuid(), nullable=True),
        _timestamp("created_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_departments")),
        sa.UniqueConstraint("name", name=op.f("uq_departments_name")),
    )
    op.create_table(
        "employees",
        _id(),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("manager_id", sa.Uuid(), nullable=True),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employees")),
        sa.UniqueConstraint("email", name=op.f("uq_employees_email")),
        sa.ForeignKeyConstraint(
            ["manager_id"], ["employees.id"], name=op.f("fk_employees_manager_id_employees")
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name=op.f("fk_employees_department_id_departments"),
        ),
    )
    op.create_index(op.f("ix_employees_manager_id"), "employees", ["manager_id"])
    op.create_index(op.f("ix_employees_department_id"), "employees", ["department_id"])

    # Dependencia circular: departments -> employees se añade cuando ya existen ambas tablas.
    op.create_foreign_key(
        op.f("fk_departments_manager_id_employees"),
        "departments",
        "employees",
        ["manager_id"],
        ["id"],
    )
    op.create_index(op.f("ix_departments_manager_id"), "departments", ["manager_id"])

    op.create_table(
        "position_history",
        _id(),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("job_title_id", sa.Uuid(), nullable=False),
        sa.Column("salary", sa.Numeric(12, 2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        _timestamp("created_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_position_history")),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name=op.f("fk_position_history_employee_id_employees"),
        ),
        sa.ForeignKeyConstraint(
            ["job_title_id"],
            ["job_titles.id"],
            name=op.f("fk_position_history_job_title_id_job_titles"),
        ),
        sa.UniqueConstraint(
            "employee_id",
            "start_date",
            name=op.f("uq_position_history_employee_id_start_date"),
        ),
        sa.CheckConstraint("salary > 0", name=op.f("ck_position_history_salary_positive")),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name=op.f("ck_position_history_valid_dates"),
        ),
    )
    op.create_index(op.f("ix_position_history_job_title_id"), "position_history", ["job_title_id"])
    op.create_index(
        "uq_position_history_active",
        "position_history",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("end_date IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("position_history")
    op.drop_constraint(
        op.f("fk_departments_manager_id_employees"), "departments", type_="foreignkey"
    )
    op.drop_table("employees")
    op.drop_table("departments")
    op.drop_table("job_titles")
