from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.core.error_handlers import register_error_handlers
from app.router import api_router
from app.seed.admin import ensure_admin


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    # Antes del yield: arranque de la app. Después: apagado.
    # En cada arranque: crea el administrador si falta o lo restaura. Es idempotente.
    async with AsyncSessionLocal.begin() as session:
        await ensure_admin(session)
    yield
    await engine.dispose()  # cierra ordenadamente las conexiones del pool


def create_app() -> FastAPI:
    app = FastAPI(title="Employee Work Tree API", version="0.1.0", lifespan=lifespan)
    register_error_handlers(app)
    # CORS: el navegador bloquea las llamadas de un front en otro origen salvo que la API
    # lo autorice. Sin credenciales (cookies): la autenticación va en el header Authorization.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=[
            "GET",
            "POST",
            "PATCH",
            "DELETE",
        ],  # OPTIONS (preflight) lo gestiona el middleware
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(api_router)

    # Healthcheck para Railway: responde 200 si el proceso está vivo. No toca la base de
    # datos a propósito, para que un fallo momentáneo de la DB no reinicie la app.
    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
