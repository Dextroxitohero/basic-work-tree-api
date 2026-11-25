"""Imprime un token del usuario admin. Uso: python -m app.modules.auth.admin_token"""

from app.core.config import get_settings
from app.modules.auth.local import ADMIN, create_token


def main() -> None:
    settings = get_settings()
    if settings.auth_mode != "local":
        raise SystemExit("Solo disponible con AUTH_MODE=local. Con Auth0, pide el token a Auth0.")
    # Se imprime únicamente el token, para poder guardarlo en una variable.
    print(
        create_token(
            ADMIN,
            settings.local_jwt_secret.get_secret_value(),
            audience=settings.auth0_audience,
        )
    )


if __name__ == "__main__":
    main()
