"""Datos de ejemplo para desarrollo. Uso: python -m app.seed

Usa los mismos servicios que la API, así los datos cumplen todas las reglas de negocio.
Es idempotente: lo que ya existe no se modifica ni se duplica.
"""

import asyncio

from app.core.database import AsyncSessionLocal, engine
from app.seed.admin import ensure_admin
from app.seed.data import PEOPLE
from app.seed.loader import seed


async def main() -> None:
    # Evita cargar empleados ficticios en una base de datos remota por error.
    if engine.url.host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("La semilla solo se ejecuta contra una base de datos local")
    # begin(): commit si todo va bien, rollback completo si algo falla.
    async with AsyncSessionLocal.begin() as session:
        await ensure_admin(session)
        created = await seed(session)
    await engine.dispose()
    print(f"Empleados creados: {created}. Ya existían: {len(PEOPLE) - created}.")


if __name__ == "__main__":
    asyncio.run(main())
