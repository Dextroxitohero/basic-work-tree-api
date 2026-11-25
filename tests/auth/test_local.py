from datetime import timedelta

import jwt
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app
from app.modules.auth.exceptions import InvalidTokenError
from app.modules.auth.local import ADMIN, LOCAL_ISSUER, LocalTokenVerifier, create_token
from app.modules.auth.verifier import get_token_verifier
from tests.conftest import ALL_PERMISSIONS

SECRET = "s" * 32
AUDIENCE = "https://employee-api"
verifier = LocalTokenVerifier(SECRET, audience=AUDIENCE)


async def test_admin_token_has_every_permission():
    payload = await verifier.verify(create_token(ADMIN, SECRET, audience=AUDIENCE))

    assert payload == ADMIN
    assert set(payload.permissions) == set(ALL_PERMISSIONS.split(","))


@pytest.mark.parametrize(
    "token",
    [
        create_token(ADMIN, "x" * 32, audience=AUDIENCE),
        create_token(ADMIN, SECRET, audience="otra"),
        create_token(ADMIN, SECRET, audience=AUDIENCE, lifetime=timedelta(seconds=-1)),
        jwt.encode({"sub": "x", "aud": AUDIENCE, "iss": LOCAL_ISSUER}, SECRET, algorithm="HS256"),
        jwt.encode({"sub": "x", "aud": AUDIENCE, "iss": LOCAL_ISSUER}, None, algorithm="none"),
        "no-es-un-jwt",
    ],
    ids=["secret", "audience", "expired", "no-exp", "alg-none", "garbage"],
)
async def test_invalid_tokens(token):
    with pytest.raises(InvalidTokenError):
        await verifier.verify(token)


async def test_admin_can_use_the_api(anonymous_client):
    app.dependency_overrides[get_token_verifier] = lambda: verifier
    token = create_token(ADMIN, SECRET, audience=AUDIENCE)

    response = await anonymous_client.post(
        "/job-titles", json={"name": "Dev"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 201


def make_settings(**overrides) -> Settings:
    # _env_file=None: el resultado no debe depender del .env de cada máquina.
    return Settings(_env_file=None, database_url="x", **overrides)


def test_auth0_is_the_default(monkeypatch):
    monkeypatch.delenv("AUTH_MODE")

    assert make_settings().auth_mode == "auth0"


@pytest.mark.parametrize("secret", [None, "corto"])
def test_local_mode_requires_a_strong_secret(secret):
    with pytest.raises(ValidationError):
        make_settings(auth_mode="local", local_jwt_secret=secret)
