"""Administrador inicial: el primer usuario con todos los permisos.

Sin él nadie podría subir permisos a los demás usuarios. Las credenciales salen de
ADMIN_EMAIL y ADMIN_PASSWORD. Es idempotente: si ya existe no se duplica, y si alguien lo
desactivó o le quitó permisos, se restaura (su contraseña no se toca).
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.auth.dependencies import get_auth_service
from app.modules.auth.service import AdminStatus

logger = logging.getLogger(__name__)


async def ensure_admin(session: AsyncSession) -> AdminStatus:
    """Crea o restaura al admin. No hace commit."""
    settings = get_settings()
    status = await get_auth_service(session).ensure_admin(
        email=settings.admin_email, password=settings.admin_password.get_secret_value()
    )
    if status == "conflict":
        # No se detiene el arranque (sería una vía para tumbar la API registrando ese email),
        # pero se avisa con claridad: sin administrador sembrado nadie gestiona los usuarios.
        logger.error(
            "ADMIN_EMAIL (%s) pertenece a una cuenta normal, que no se promociona a "
            "administrador. Usa otro ADMIN_EMAIL o borra esa cuenta y reinicia.",
            settings.admin_email,
        )
    return status
