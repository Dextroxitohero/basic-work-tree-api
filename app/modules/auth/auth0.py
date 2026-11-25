import jwt
from fastapi.concurrency import run_in_threadpool
from jwt import PyJWKClient

from app.modules.auth.exceptions import AuthProviderUnavailableError, InvalidTokenError
from app.modules.auth.schemas import TokenPayload


class Auth0TokenVerifier:
    def __init__(self, jwk_client: PyJWKClient, *, audience: str, issuer: str) -> None:
        self._jwk_client = jwk_client
        self._audience = audience
        self._issuer = issuer

    async def verify(self, token: str) -> TokenPayload:
        try:
            # PyJWKClient usa HTTP síncrono. run_in_threadpool lo ejecuta en otro hilo para
            # no bloquear el event loop (y con él, todos los demás requests).
            key = await run_in_threadpool(self._jwk_client.get_signing_key_from_jwt, token)
            # decode comprueba firma, expiración, audience e issuer. Fijar algorithms es
            # obligatorio: nunca se debe confiar en el algoritmo que declara el propio token.
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWKClientConnectionError as exc:
            # Auth0 no responde: no es culpa del token, por eso no es un 401.
            raise AuthProviderUnavailableError() from exc
        except jwt.PyJWTError as exc:
            raise InvalidTokenError() from exc
        return TokenPayload(
            sub=claims["sub"],
            email=claims.get("email"),
            # Requiere activar RBAC y "Add Permissions in the Access Token" en Auth0.
            permissions=claims.get("permissions", []),
        )
