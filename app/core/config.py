from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # "local" es SOLO para desarrollo: quien tenga el secreto puede crear tokens de admin.
    auth_mode: Literal["auth0", "local"] = "auth0"
    # SecretStr se muestra como ********** si se imprime, para que no acabe en un log.
    local_jwt_secret: Annotated[SecretStr | None, Field(min_length=32)] = None

    auth0_domain: str
    auth0_audience: str

    debug: bool = False

    # extra="ignore": el .env puede tener variables que la app no usa (DATABASE_URL_TEST).
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def local_mode_requires_secret(self) -> Self:
        if self.auth_mode == "local" and self.local_jwt_secret is None:
            raise ValueError("AUTH_MODE=local requiere LOCAL_JWT_SECRET")
        return self


@lru_cache
def get_settings() -> Settings:
    # lru_cache lo convierte en un singleton perezoso: el .env se lee una sola vez.
    return Settings()
