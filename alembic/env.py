import asyncio

from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from alembic import context
from app.core.config import get_settings
from app.models import Base


def run_migrations(connection: Connection) -> None:
    # target_metadata permite a Alembic comparar los modelos con la DB (autogenerate / check).
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # NullPool: una migración usa una sola conexión, no necesita pool.
    engine = create_async_engine(
        get_settings().database_url, poolclass=NullPool, hide_parameters=True
    )
    async with engine.connect() as connection:
        # Alembic es síncrono; run_sync hace de puente con el driver async.
        await connection.run_sync(run_migrations)
    await engine.dispose()


asyncio.run(run_migrations_online())
