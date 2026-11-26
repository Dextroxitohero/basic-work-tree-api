"""JWT propios: emisión y verificación. Sin base de datos."""

from datetime import timedelta
from uuid import uuid4

import jwt
import pytest

from app.modules.auth.exceptions import InvalidTokenError
from app.modules.auth.models import User
from app.modules.auth.permissions import ALL_PERMISSIONS
from app.modules.auth.tokens import AUDIENCE, ISSUER, JwtTokens

SECRET = "s" * 32
tokens = JwtTokens(SECRET)


def make_user() -> User:
    return User(
        id=uuid4(),
        email="ana@example.com",
        full_name="Ana",
        password_hash="x",
        is_active=True,
        permissions=list(ALL_PERMISSIONS),
    )


def forge(secret=SECRET, algorithm="HS256", **overrides) -> str:
    import time

    claims = {
        "sub": str(uuid4()),
        "aud": AUDIENCE,
        "iss": ISSUER,
        "exp": time.time() + 60,
    }
    merged = {k: v for k, v in (claims | overrides).items() if v is not None}
    return jwt.encode(merged, secret, algorithm=algorithm)


def test_issued_token_has_the_expected_claims_and_lifetime():
    user = make_user()

    token, expires_in = tokens.issue(user)
    claims = jwt.decode(token, SECRET, algorithms=["HS256"], audience=AUDIENCE)

    assert expires_in == 12 * 3600
    assert claims["sub"] == str(user.id)
    assert claims["email"] == user.email
    assert claims["iss"] == ISSUER
    assert claims["aud"] == AUDIENCE
    assert claims["permissions"] == list(ALL_PERMISSIONS)
    assert claims["exp"] - claims["iat"] == 12 * 3600


def test_verify_returns_the_payload():
    user = make_user()
    token, _ = tokens.issue(user)

    payload = tokens.verify(token)

    assert payload.sub == user.id
    assert payload.email == user.email
    assert payload.permissions == list(ALL_PERMISSIONS)


@pytest.mark.parametrize(
    "token",
    [
        forge(secret="x" * 32),
        forge(aud="otra-api"),
        forge(iss="otro-emisor"),
        forge(exp=1),
        forge(exp=None),
        forge(sub=None),
        forge(sub="no-es-un-uuid"),
        forge(aud=None),
        jwt.encode({"sub": str(uuid4()), "aud": AUDIENCE, "iss": ISSUER}, None, algorithm="none"),
        "no-es-un-jwt",
        "",
    ],
    ids=[
        "secret",
        "audience",
        "issuer",
        "expired",
        "no-exp",
        "no-sub",
        "sub-not-uuid",
        "no-aud",
        "alg-none",
        "garbage",
        "empty",
    ],
)
def test_invalid_tokens_are_rejected(token):
    with pytest.raises(InvalidTokenError):
        tokens.verify(token)


def test_expired_token_is_rejected():
    short = JwtTokens(SECRET, lifetime=timedelta(seconds=-1))
    token, _ = short.issue(make_user())

    with pytest.raises(InvalidTokenError):
        tokens.verify(token)


@pytest.mark.filterwarnings("ignore:The HMAC key")
def test_a_different_hmac_algorithm_is_rejected():
    # El algoritmo lo decide la API (HS256), no el token.
    with pytest.raises(InvalidTokenError):
        tokens.verify(forge(algorithm="HS512"))
