"""Administrador inicial: el primer usuario con todos los permisos.

Sin él nadie podría subir permisos a los demás usuarios. Las credenciales salen de
ADMIN_EMAIL y ADMIN_PASSWORD. Es idempotente: si ya existe no se duplica, y si alguien lo
desactivó o le quitó permisos, se restaura (su contraseña no se toca).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.auth.dependencies import get_auth_service


async def ensure_admin(session: AsyncSession) -> None:
    """Crea o restaura al admin. No hace commit."""
    settings = get_settings()
    await get_auth_service(session).ensure_admin(
        email=settings.admin_email, password=settings.admin_password.get_secret_value()
    )
