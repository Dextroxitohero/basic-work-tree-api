"""Hash de contraseñas con Argon2id (argon2-cffi).

Argon2id es el algoritmo recomendado por OWASP: es lento y consume memoria a propósito, para
que probar millones de contraseñas contra un hash robado sea carísimo.
"""

import asyncio
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


class Argon2PasswordHasher:
    """Cumple el Protocol PasswordHasher, sin heredar de él."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher()  # argon2id con los parámetros por defecto de la librería
        # Hash de una contraseña al azar. Si el email no existe se verifica contra él, para que
        # login tarde igual con un email registrado que con uno que no lo está.
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(32))

    async def hash(self, password: str) -> str:
        # El hash tarda decenas de milisegundos de CPU: se ejecuta en otro hilo para no
        # bloquear el event loop (y con él, todos los demás requests).
        return await asyncio.to_thread(self._hasher.hash, password)

    async def verify(self, password: str, password_hash: str | None) -> bool:
        target = password_hash if password_hash is not None else self._dummy_hash
        try:
            await asyncio.to_thread(self._hasher.verify, target, password)
        except (VerificationError, InvalidHashError):
            return False
        # Con el hash falso nunca coincide, pero se hizo el mismo trabajo.
        return password_hash is not None
