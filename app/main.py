import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import engine
from app.core.error_handlers import register_error_handlers
from app.router import api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    # Antes del yield: arranque de la app. Después: apagado.
    if get_settings().auth_mode == "local":
        logger.warning("AUTH_MODE=local: autenticación de desarrollo, no usar en producción")
    yield
    await engine.dispose()  # cierra ordenadamente las conexiones del pool


def create_app() -> FastAPI:
    app = FastAPI(title="Employee Work Tree API", version="0.1.0", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(api_router)

    # Healthcheck para Railway: responde 200 si el proceso está vivo. No toca la base de
    # datos a propósito, para que un fallo momentáneo de la DB no reinicie la app.
    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
