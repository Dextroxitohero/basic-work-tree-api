"""La configuración de autenticación no tiene valores por defecto."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

VALID = {
    "database_url": "postgresql://u:p@h/db",
    "jwt_secret": "s" * 32,
    "admin_email": "admin@example.com",
    "admin_password": "p" * 12,
}


def make_settings(**overrides) -> Settings:
    # _env_file=None y sin variables de entorno: el resultado no depende de cada máquina.
    return Settings(_env_file=None, **(VALID | overrides))


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("JWT_SECRET", "ADMIN_EMAIL", "ADMIN_PASSWORD", "DATABASE_URL"):
        monkeypatch.delenv(name)


def test_valid_settings():
    settings = make_settings()

    assert settings.jwt_secret.get_secret_value() == "s" * 32
    assert settings.admin_password.get_secret_value() == "p" * 12


@pytest.mark.parametrize("missing", ["jwt_secret", "admin_email", "admin_password"])
def test_the_app_does_not_start_without_auth_settings(missing):
    values = {k: v for k, v in VALID.items() if k != missing}

    with pytest.raises(ValidationError, match=missing):
        Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("jwt_secret", "s" * 31),
        ("admin_password", "p" * 11),
        ("admin_email", "no-es-un-email"),
    ],
)
def test_weak_or_invalid_values_are_rejected(name, value):
    with pytest.raises(ValidationError):
        make_settings(**{name: value})


def test_admin_email_is_normalized():
    assert make_settings(admin_email="  Admin@Example.COM ").admin_email == "admin@example.com"


def test_secrets_are_not_shown_when_printed():
    settings = make_settings()

    assert "s" * 32 not in repr(settings)
    assert "p" * 12 not in repr(settings)


def test_old_auth0_variables_are_ignored(monkeypatch):
    monkeypatch.setenv("AUTH0_DOMAIN", "x.auth0.com")
    monkeypatch.setenv("AUTH_MODE", "local")

    assert make_settings().jwt_secret.get_secret_value() == "s" * 32
