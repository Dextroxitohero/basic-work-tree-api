import os
import subprocess
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from dotenv import dotenv_values
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

ROOT = Path(__file__).parent.parent

# Debe ejecutarse ANTES de importar la app: database.py crea el engine al importarse.
# Las variables de entorno tienen prioridad sobre el archivo .env.
# La URL de tests puede estar en .env o en .env.dev (el entorno de desarrollo).
_files = {**dotenv_values(ROOT / ".env"), **dotenv_values(ROOT / ".env.dev")}
_test_url = os.environ.get("DATABASE_URL_TEST") or _files.get("DATABASE_URL_TEST")
# Los tests vacían las tablas: esta comprobación evita borrar datos reales por error.
if not _test_url or not _test_url.endswith("_test"):
    raise RuntimeError("DATABASE_URL_TEST debe apuntar a una base de datos terminada en _test")
os.environ["DATABASE_URL"] = _test_url
# Los tests siempre corren en dev, aunque el .env de esta máquina diga otra cosa.
os.environ["APP_ENV"] = "dev"
os.environ["JWT_SECRET"] = "secreto-solo-para-tests-" + "x" * 24
os.environ["ADMIN_EMAIL"] = "Admin@Example.com"  # con mayúsculas: debe guardarse en minúsculas
os.environ["ADMIN_PASSWORD"] = "contraseña-del-admin-123"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, User  # noqa: E402
from app.modules.auth.dependencies import get_password_hasher  # noqa: E402
from app.modules.auth.guard import get_auth_guard  # noqa: E402
from app.modules.auth.permissions import ALL_PERMISSIONS  # noqa: E402
from app.modules.auth.tokens import get_tokens  # noqa: E402

# La contraseña de todos los usuarios que crea la fixture make_user.
TEST_PASSWORD = "contraseña-de-prueba-1"

Factory = Callable[..., Awaitable[dict[str, Any]]]


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    # Se usan las migraciones reales (no create_all), así también quedan probadas.
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True)


@pytest.fixture(scope="session", autouse=True)
async def dispose_engine() -> AsyncGenerator[None]:
    yield
    await engine.dispose()


@pytest.fixture(scope="session")
async def password_hash() -> str:
    # Argon2 es lento a propósito: se calcula UNA vez y se reutiliza para todos los usuarios.
    return await get_password_hasher().hash(TEST_PASSWORD)


@pytest.fixture
async def anonymous_client() -> AsyncGenerator[AsyncClient]:
    tables = ", ".join(Base.metadata.tables)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} CASCADE"))
    # Los contadores del límite de intentos viven en memoria: cada test empieza de cero.
    get_auth_guard().clear()

    # ASGITransport llama a la app directamente en memoria, sin abrir un puerto.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield client


@pytest.fixture
def make_user(anonymous_client: AsyncClient, password_hash: str) -> Factory:
    """Crea un usuario real en la base y devuelve su token (emitido por la propia API)."""
    counter = 0

    async def create(
        *,
        permissions: tuple[str, ...] | list[str] = ALL_PERMISSIONS,
        email: str | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        nonlocal counter
        counter += 1
        email = email or f"user{counter}@example.com"
        async with AsyncSessionLocal.begin() as session:
            user = User(
                email=email,
                full_name=f"Usuario {counter}",
                password_hash=password_hash,
                is_active=is_active,
                permissions=list(permissions),
            )
            session.add(user)
            await session.flush()
            token, _ = get_tokens().issue(user)
            user_id = str(user.id)
        return {
            "id": user_id,
            "email": email,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
        }

    return create


@pytest.fixture
async def admin(make_user: Factory) -> dict[str, Any]:
    return await make_user(permissions=ALL_PERMISSIONS)


@pytest.fixture
async def client(anonymous_client: AsyncClient, admin: dict[str, Any]) -> AsyncClient:
    """Cliente autenticado con todos los permisos."""
    anonymous_client.headers.update(admin["headers"])
    return anonymous_client


@pytest.fixture
def get_all(client: AsyncClient) -> Callable[..., Awaitable[list[dict[str, Any]]]]:
    """Recorre todas las páginas de un listado paginado, siguiendo next_cursor."""

    async def fetch(path: str, **params: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        after = None
        while True:
            query = params | ({"after": after} if after else {})
            response = await client.get(path, params=query)
            assert response.status_code == 200, response.text
            page = response.json()
            items += page["items"]
            after = page["next_cursor"]
            if after is None:
                return items

    return fetch


@pytest.fixture
def create_employee(client: AsyncClient) -> Factory:
    counter = 0

    async def create(**overrides: Any) -> dict[str, Any]:
        nonlocal counter
        counter += 1
        body = {
            "first_name": "Ana",
            "last_name": f"Apellido{counter}",
            "email": f"ana{counter}@example.com",
            "hire_date": "2020-01-01",
        }
        response = await client.post("/employees", json=body | overrides)
        assert response.status_code == 201, response.text
        return response.json()

    return create


@pytest.fixture
def create_job_title(client: AsyncClient) -> Factory:
    async def create(name: str = "Developer") -> dict[str, Any]:
        response = await client.post("/job-titles", json={"name": name})
        assert response.status_code == 201, response.text
        return response.json()

    return create


@pytest.fixture
def assign_position(client: AsyncClient) -> Factory:
    async def assign(employee_id: str, job_title_id: str, start_date: str) -> dict[str, Any]:
        response = await client.post(
            f"/employees/{employee_id}/positions",
            json={"job_title_id": job_title_id, "salary": "1500.50", "start_date": start_date},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return assign
