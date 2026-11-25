from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

# El engine es dueño del pool. Se crea UNA vez por proceso: crear uno por request
# abriría conexiones nuevas cada vez y anularía el pool.
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,  # conexiones que se mantienen abiertas
    max_overflow=settings.database_max_overflow,  # extra permitidas en picos
    pool_timeout=settings.database_pool_timeout,  # segundos esperando una conexión libre
    pool_recycle=settings.database_pool_recycle,  # renueva conexiones viejas
    pool_pre_ping=True,  # comprueba que la conexión siga viva antes de usarla
    echo=settings.debug,  # imprime el SQL solo en desarrollo
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    # Tras el commit los objetos siguen siendo legibles sin lanzar otro query.
    expire_on_commit=False,
    # Los repositorios hacen flush() explícito, para traducir ahí los errores de constraints.
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Una sesión (= una transacción) por request."""
    # async with devuelve la conexión al pool siempre, haya o no excepción.
    async with AsyncSessionLocal() as session:
        try:
            # FastAPI inyecta lo que va en el yield y retoma aquí cuando termina el endpoint.
            yield session
            await session.commit()
        except Exception:
            # Si algo falló se deshace todo: nunca quedan cambios a medias.
            await session.rollback()
            raise


# scope="function": el commit de get_db ocurre ANTES de enviar la respuesta. Con el scope por
# defecto ("request") ocurre después, y el cliente podría recibir un 201 de algo no guardado.
# FastAPI cachea la dependencia dentro de un request: todos los módulos comparten la misma
# sesión y, por tanto, la misma transacción.
DbSession = Annotated[AsyncSession, Depends(get_db, scope="function")]
