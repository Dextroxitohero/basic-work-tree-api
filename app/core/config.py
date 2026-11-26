from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración leída de variables de entorno (o del archivo .env).

    Pydantic valida los tipos al arrancar: si falta DATABASE_URL, la app falla de inmediato
    con un mensaje claro, en vez de fallar en el primer request.
    """

    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 5
    database_pool_timeout: int = 30
    database_pool_recycle: int = 1800

    # Secretos SIN valor por defecto: si faltan, la app no arranca. Un valor por defecto
    # conocido permitiría fabricar tokens de admin o entrar con una contraseña pública.
    # SecretStr se muestra como ********** si se imprime, para que no acabe en un log.
    jwt_secret: Annotated[SecretStr, Field(min_length=32)]
    admin_email: str
    admin_password: Annotated[SecretStr, Field(min_length=12)]

    debug: bool = False

    # Orígenes del front que pueden llamar a la API desde el navegador, separados por comas:
    # CORS_ORIGINS=http://localhost:5173,https://mi-front.up.railway.app
    # NoDecode evita que pydantic-settings intente leerlo como JSON.
    cors_origins: Annotated[list[str], NoDecode] = []

    # extra="ignore": el .env puede tener variables que la app no usa (DATABASE_URL_TEST).
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("admin_email")
    @classmethod
    def normalize_admin_email(cls, value: str) -> str:
        # Los emails se guardan siempre en minúsculas (ver users.email).
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("ADMIN_EMAIL debe ser un email")
        return email

    @field_validator("database_url")
    @classmethod
    def use_asyncpg_driver(cls, value: str) -> str:
        """Railway (y Heroku) entregan la URL como postgres:// o postgresql://.

        SQLAlchemy async necesita el driver en el esquema (postgresql+asyncpg://), así que
        lo añadimos aquí. Si la URL ya lo trae (desarrollo local), no se toca.
        """
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+asyncpg://" + value.removeprefix(prefix)
        return value


@lru_cache
def get_settings() -> Settings:
    # lru_cache lo convierte en un singleton perezoso: el .env se lee una sola vez.
    return Settings()
