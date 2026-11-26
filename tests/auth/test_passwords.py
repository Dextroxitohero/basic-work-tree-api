"""Hash de contraseñas con Argon2id. Sin base de datos."""

from app.modules.auth.passwords import Argon2PasswordHasher

hasher = Argon2PasswordHasher()


async def test_hash_is_argon2id_and_does_not_contain_the_password():
    password_hash = await hasher.hash("mi-contraseña-secreta")

    assert password_hash.startswith("$argon2id$")
    assert "mi-contraseña-secreta" not in password_hash


async def test_same_password_gets_a_different_hash_each_time():
    assert await hasher.hash("repetida-123") != await hasher.hash("repetida-123")


async def test_verify_accepts_the_right_password_only():
    password_hash = await hasher.hash("correcta-123")

    assert await hasher.verify("correcta-123", password_hash) is True
    assert await hasher.verify("incorrecta-123", password_hash) is False


async def test_verify_with_a_corrupt_hash_is_false_not_an_error():
    assert await hasher.verify("lo-que-sea", "esto-no-es-un-hash") is False


async def test_unknown_user_still_costs_one_hash_verification(monkeypatch):
    # Sin email registrado no hay hash, pero se verifica igual contra uno falso: el tiempo
    # de respuesta no delata qué emails existen.
    calls = []

    class CountingHasher:
        def __init__(self, real):
            self._real = real

        def verify(self, *args):
            calls.append(args)
            return self._real.verify(*args)

    monkeypatch.setattr(hasher, "_hasher", CountingHasher(hasher._hasher))

    assert await hasher.verify("cualquiera-123", None) is False
    assert len(calls) == 1
