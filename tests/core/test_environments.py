"""La bandera APP_ENV elige el archivo de configuración y activa las reglas de production."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, build_settings, selected_environment

# Todas las variables que pueden venir del entorno de la máquina que ejecuta los tests.
VARIABLES = (
    "APP_ENV",
    "DATABASE_URL",
    "JWT_SECRET",
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "CORS_ORIGINS",
    "DEBUG",
    "TRUSTED_PROXY_HOPS",
)

COMMON = {
    "JWT_SECRET": "s" * 32,
    "ADMIN_EMAIL": "admin@example.com",
    "ADMIN_PASSWORD": "p" * 12,
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)


def write_env(directory, name: str, **values) -> None:
    (directory / name).write_text("\n".join(f"{k}={v}" for k, v in values.items()))


@pytest.fixture
def project(tmp_path):
    """Un proyecto con sus tres archivos, como los dejaría el desarrollador."""
    write_env(tmp_path, ".env", **COMMON)
    write_env(
        tmp_path,
        ".env.dev",
        DATABASE_URL="postgresql://u:p@localhost:5440/dev_db",
        CORS_ORIGINS="http://localhost:5173",
        DEBUG="true",
    )
    write_env(
        tmp_path,
        ".env.production",
        DATABASE_URL="postgresql://u:p@db.railway.internal:5432/prod_db",
        CORS_ORIGINS="https://front.example.com",
        TRUSTED_PROXY_HOPS="1",
    )
    return tmp_path


# ---------------------------------------------------------------- la bandera elige el entorno


def test_dev_is_the_default(project):
    settings = build_settings(project)

    assert settings.app_env == "dev"
    assert "dev_db" in settings.database_url
    assert settings.cors_origins == ["http://localhost:5173"]
    assert settings.debug is True


def test_the_flag_in_the_env_file_selects_production(project):
    write_env(project, ".env", **COMMON, APP_ENV="production")

    settings = build_settings(project)

    assert settings.app_env == "production"
    assert "prod_db" in settings.database_url
    assert settings.cors_origins == ["https://front.example.com"]
    assert settings.trusted_proxy_hops == 1
    assert settings.debug is False


def test_the_flag_in_the_real_environment_wins_over_the_env_file(project, monkeypatch):
    write_env(project, ".env", **COMMON, APP_ENV="dev")
    monkeypatch.setenv("APP_ENV", "production")

    assert build_settings(project).app_env == "production"


def test_switching_only_the_flag_switches_all_the_links(project, monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    dev = build_settings(project)
    monkeypatch.setenv("APP_ENV", "production")
    production = build_settings(project)

    assert dev.database_url != production.database_url
    assert dev.cors_origins != production.cors_origins


def test_real_environment_variables_win_over_every_file(project, monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("CORS_ORIGINS", "http://otro.example.com")

    assert build_settings(project).cors_origins == ["http://otro.example.com"]


def test_env_environment_file_overrides_the_common_one(project):
    write_env(project, ".env", **COMMON, DEBUG="false")  # .env.dev dice DEBUG=true

    assert build_settings(project).debug is True


def test_production_works_without_files_like_in_railway(tmp_path, monkeypatch):
    # Railway define las variables en el panel: no hay ningún archivo.
    for name, value in {
        **COMMON,
        "APP_ENV": "production",
        "DATABASE_URL": "postgres://u:p@db.railway.internal:5432/railway",
        "CORS_ORIGINS": "https://front.example.com",
    }.items():
        monkeypatch.setenv(name, value)

    settings = build_settings(tmp_path)

    assert settings.app_env == "production"
    assert settings.database_url.startswith("postgresql+asyncpg://")


@pytest.mark.parametrize("value", ["staging", "prod", "", "  "])
def test_unknown_environment_is_rejected(project, monkeypatch, value):
    monkeypatch.setenv("APP_ENV", value)

    if value.strip() == "":
        # Una bandera vacía cuenta como no puesta: se usa el valor por defecto.
        assert selected_environment(project) == "dev"
    else:
        with pytest.raises(ValueError, match="APP_ENV"):
            build_settings(project)


def test_environment_name_is_case_insensitive(project, monkeypatch):
    monkeypatch.setenv("APP_ENV", " Production ")

    assert selected_environment(project) == "production"


def test_a_contradicting_file_is_rejected(project):
    # .env.dev se carga porque la bandera es dev, pero él mismo dice production.
    write_env(project, ".env.dev", DATABASE_URL="postgresql://u:p@h/db", APP_ENV="production")

    with pytest.raises(ValueError, match="APP_ENV"):
        build_settings(project)


# ---------------------------------------------------------------- reglas de production


def make_settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "database_url": "postgres://u:p@db.railway.internal:5432/railway",
        "jwt_secret": "s" * 32,
        "admin_email": "admin@example.com",
        "admin_password": "p" * 12,
        "cors_origins": "https://front.example.com",
    }
    return Settings(_env_file=None, **(values | overrides))


def test_a_valid_production_configuration():
    settings = make_settings()

    assert settings.app_env == "production"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"debug": True}, "DEBUG"),
        ({"cors_origins": "*"}, "CORS_ORIGINS"),
        ({"cors_origins": "https://front.example.com,*"}, "CORS_ORIGINS"),
        ({"database_url": "postgresql://u:p@localhost:5440/db"}, "DATABASE_URL"),
        ({"database_url": "postgresql+asyncpg://u:p@127.0.0.1/db"}, "DATABASE_URL"),
        ({"database_url": "postgresql://u:p@[::1]/db"}, "DATABASE_URL"),
    ],
)
def test_production_refuses_dangerous_settings(overrides, message):
    with pytest.raises(ValidationError, match=message):
        make_settings(**overrides)


def test_production_reports_every_problem_at_once():
    with pytest.raises(ValidationError) as error:
        make_settings(debug=True, cors_origins="*", database_url="postgresql://u:p@localhost/db")

    text = str(error.value)
    assert "DEBUG" in text and "CORS_ORIGINS" in text and "DATABASE_URL" in text


def test_dev_allows_all_of_that():
    settings = make_settings(
        app_env="dev",
        debug=True,
        cors_origins="*",
        database_url="postgresql://u:p@localhost:5440/db",
    )

    assert settings.app_env == "dev"
    assert settings.debug is True
