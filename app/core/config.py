import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from dotenv import dotenv_values
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# La "bandera": APP_ENV decide qué archivo de configuración se carga (.env.dev o
# .env.production) y activa las comprobaciones de seguridad de production.
Environment = Literal["dev", "production"]
ENVIRONMENTS: tuple[str, ...] = ("dev", "production")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class Settings(BaseSettings):
    """Configuración leída de variables de entorno (o del archivo .env).

    Pydantic valida los tipos al arrancar: si falta DATABASE_URL, la app falla de inmediato
    con un mensaje claro, en vez de fallar en el primer request.
    """

    # dev (por defecto) o production. Con production la app rechaza configuraciones peligrosas
    # (ver production_guardrails). La imagen Docker la fija en production.
    app_env: Environment = "dev"

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

    # Cuántos proxies de confianza hay delante de la app (Railway: 1). Con 0 se usa la IP de la
    # conexión y se ignora X-Forwarded-For. Ver core/client_ip.py. El Dockerfile lo pone en 1.
    trusted_proxy_hops: Annotated[int, Field(ge=0, le=5)] = 0

    # Orígenes del front que pueden llamar a la API desde el navegador, separados por comas:
    # CORS_ORIGINS=http://localhost:5173,https://mi-front.up.railway.app
    # NoDecode evita que pydantic-settings intente leerlo como JSON.
    cors_origins: Annotated[list[str], NoDecode] = []

    # extra="ignore": el .env puede tener variables que la app no usa (DATABASE_URL_TEST).
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def production_guardrails(self) -> Self:
        """En production, errores de configuración típicos tumban la app en el arranque.

        Es mejor que la app no arranque a que arranque en producción con la base de datos
        local, mostrando el SQL en los logs o aceptando peticiones desde cualquier origen.
        """
        if self.app_env != "production":
            return self
        problems = []
        if self.debug:
            problems.append("DEBUG debe ser false (muestra el SQL en los logs)")
        if "*" in self.cors_origins:
            problems.append("CORS_ORIGINS no puede ser * (lista los orígenes del front)")
        if urlsplit(self.database_url).hostname in LOCAL_HOSTS:
            problems.append("DATABASE_URL apunta a una base de datos local")
        if problems:
            raise ValueError("Configuración no válida para production: " + "; ".join(problems))
        return self

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


def selected_environment(directory: Path) -> str:
    """El entorno elegido por la bandera APP_ENV: variable de entorno, luego .env, luego dev."""
    value = os.environ.get("APP_ENV") or dotenv_values(directory / ".env").get("APP_ENV") or ""
    value = value.strip().lower() or "dev"  # vacío = no puesta
    if value not in ENVIRONMENTS:
        raise ValueError(f"APP_ENV debe ser uno de {ENVIRONMENTS}, no {value!r}")
    return value


def build_settings(directory: Path = Path(".")) -> Settings:
    """Carga la configuración del entorno elegido.

    Orden de prioridad, de menor a mayor: .env, .env.<entorno> y las variables de entorno
    reales (en Railway se definen en el panel, sin archivos). Así `.env` guarda lo común
    (incluida la bandera APP_ENV) y cada entorno solo lo suyo: la base de datos, los orígenes
    permitidos, etc.
    """
    environment = selected_environment(directory)
    settings = Settings(_env_file=(directory / ".env", directory / f".env.{environment}"))
    if settings.app_env != environment:
        # Por ejemplo, .env.dev con APP_ENV=production: la bandera se contradice.
        raise ValueError(
            f"APP_ENV es '{environment}' pero la configuración cargada dice '{settings.app_env}'"
        )
    return settings


@lru_cache
def get_settings() -> Settings:
    # lru_cache lo convierte en un singleton perezoso: la configuración se lee una sola vez.
    return build_settings()
