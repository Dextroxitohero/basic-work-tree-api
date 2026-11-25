from collections.abc import Mapping

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError


async def flush(session: AsyncSession, conflicts: Mapping[str, type[ConflictError]]) -> None:
    """Envía los cambios a la DB (sin commit) y traduce violaciones de unicidad.

    conflicts relaciona el nombre de un constraint con su error. Lo aporta cada módulo, así
    el núcleo no necesita conocer a ninguno.

    No hacemos "SELECT para ver si existe y luego INSERT": entre ambos pasos otro request
    podría insertar lo mismo. Dejamos que decida el constraint, que es atómico.
    """
    try:
        await session.flush()
    except IntegrityError as exc:
        # SQLAlchemy envuelve el error del driver; el original de asyncpg está en __cause__.
        constraint = getattr(exc.orig.__cause__, "constraint_name", None)
        error = conflicts.get(constraint)
        if error is None:
            raise
        raise error() from exc
