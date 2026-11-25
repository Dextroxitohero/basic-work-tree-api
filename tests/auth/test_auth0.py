import time
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.modules.auth.auth0 import Auth0TokenVerifier
from app.modules.auth.exceptions import AuthProviderUnavailableError, InvalidTokenError

AUDIENCE = "https://employee-api"
ISSUER = "https://tenant.auth0.local/"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class LocalJWKClient(jwt.PyJWKClient):
    """El cliente real de PyJWT; solo se sustituye la descarga por HTTP."""

    def fetch_data(self):
        jwk = RSAAlgorithm.to_jwk(KEY.public_key(), as_dict=True)
        return {"keys": [jwk | {"kid": "key-1", "use": "sig", "alg": "RS256"}]}


class OfflineJWKClient(jwt.PyJWKClient):
    def fetch_data(self):
        raise jwt.PyJWKClientConnectionError("sin conexión")


def make_token(key=KEY, kid="key-1", **overrides) -> str:
    claims = {
        "sub": "auth0|1",
        "aud": AUDIENCE,
        "iss": ISSUER,
        "exp": time.time() + 60,
        "permissions": ["employees:read"],
    }
    merged = {k: v for k, v in (claims | overrides).items() if v is not None}
    return jwt.encode(merged, key, algorithm="RS256", headers={"kid": kid})


def make_verifier(client_class=LocalJWKClient) -> Auth0TokenVerifier:
    return Auth0TokenVerifier(client_class("https://unused"), audience=AUDIENCE, issuer=ISSUER)


async def test_valid_token():
    payload = await make_verifier().verify(make_token())

    assert payload.sub == "auth0|1"
    assert payload.permissions == ["employees:read"]


@pytest.mark.parametrize(
    "token",
    [
        make_token(exp=time.time() - 10),
        make_token(exp=None),
        make_token(aud="https://otra-api"),
        make_token(iss="https://otro-tenant/"),
        make_token(key=OTHER_KEY),
        make_token(kid="otra-clave"),
        jwt.encode(
            {"sub": "x", "aud": AUDIENCE, "iss": ISSUER},
            None,
            algorithm="none",
            headers={"kid": "key-1"},
        ),
        "no-es-un-jwt",
    ],
    ids=[
        "expired",
        "no-exp",
        "audience",
        "issuer",
        "signature",
        "unknown-kid",
        "alg-none",
        "garbage",
    ],
)
async def test_invalid_tokens(token):
    with pytest.raises(InvalidTokenError):
        await make_verifier().verify(token)


async def test_provider_down_is_not_an_invalid_token():
    with pytest.raises(AuthProviderUnavailableError):
        await make_verifier(OfflineJWKClient).verify(make_token())


async def test_missing_token_is_401(anonymous_client):
    response = await anonymous_client.get("/employees")

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    ("method", "path", "permission"),
    [
        ("GET", "/employees", "employees:read"),
        ("GET", "/employees/{id}", "employees:read"),
        ("GET", "/employees/{id}/reports", "employees:read"),
        ("GET", "/employees/{id}/tree", "employees:read"),
        ("POST", "/employees", "employees:write"),
        ("PATCH", "/employees/{id}", "employees:write"),
        ("DELETE", "/employees/{id}", "employees:write"),
        ("GET", "/employees/{id}/positions", "employees:read"),
        ("GET", "/employees/{id}/positions/current", "employees:read"),
        ("POST", "/employees/{id}/positions", "positions:write"),
        ("GET", "/job-titles", "employees:read"),
        ("GET", "/job-titles/{id}", "employees:read"),
        ("POST", "/job-titles", "job-titles:write"),
        ("PATCH", "/job-titles/{id}", "job-titles:write"),
        ("GET", "/departments", "employees:read"),
        ("GET", "/departments/{id}", "employees:read"),
        ("POST", "/departments", "departments:write"),
        ("PATCH", "/departments/{id}", "departments:write"),
    ],
)
async def test_every_endpoint_requires_its_permission(anonymous_client, method, path, permission):
    all_permissions = {
        "employees:read",
        "employees:write",
        "positions:write",
        "job-titles:write",
        "departments:write",
    }
    url = path.format(id=uuid4())
    others = ",".join(all_permissions - {permission})

    without = await anonymous_client.request(
        method, url, headers={"Authorization": f"Bearer {others}"}
    )
    with_it = await anonymous_client.request(
        method, url, headers={"Authorization": f"Bearer {permission}"}
    )

    assert without.status_code == 403
    assert without.json()["details"] == {"required": permission}
    assert with_it.status_code not in (401, 403)


async def test_framework_errors_use_the_same_contract(client):
    response = await client.get("/no-existe")

    assert response.status_code == 404
    assert response.json() == {"error": "http_error", "message": "Not Found", "details": None}
