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
_test_url = os.environ.get("DATABASE_URL_TEST") or dotenv_values(ROOT / ".env").get(
    "DATABASE_URL_TEST"
)
# Los tests vacían las tablas: esta comprobación evita borrar datos reales por error.
if not _test_url or not _test_url.endswith("_test"):
    raise RuntimeError("DATABASE_URL_TEST debe apuntar a una base de datos terminada en _test")
os.environ["DATABASE_URL"] = _test_url
os.environ["AUTH_MODE"] = "auth0"
os.environ["AUTH0_DOMAIN"] = "test.auth0.local"
os.environ["AUTH0_AUDIENCE"] = "https://employee-api"

from app.core.database import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.modules.auth.schemas import TokenPayload  # noqa: E402
from app.modules.auth.verifier import get_token_verifier  # noqa: E402

ALL_PERMISSIONS = (
    "employees:read,employees:write,positions:write,job-titles:write,departments:write"
)

Factory = Callable[..., Awaitable[dict[str, Any]]]


class FakeTokenVerifier:
    """En los tests el token ES la lista de permisos, separados por comas."""

    async def verify(self, token: str) -> TokenPayload:
        return TokenPayload(sub="test-user", permissions=token.split(","))


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    # Se usan las migraciones reales (no create_all), así también quedan probadas.
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True)


@pytest.fixture(scope="session", autouse=True)
async def dispose_engine() -> AsyncGenerator[None]:
    yield
    await engine.dispose()


@pytest.fixture
async def anonymous_client() -> AsyncGenerator[AsyncClient]:
    tables = ", ".join(Base.metadata.tables)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} CASCADE"))

    # dependency_overrides: FastAPI sustituye una dependencia sin tocar el código de la app.
    app.dependency_overrides[get_token_verifier] = FakeTokenVerifier
    # ASGITransport llama a la app directamente en memoria, sin abrir un puerto.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def client(anonymous_client: AsyncClient) -> AsyncClient:
    """Cliente autenticado con todos los permisos."""
    anonymous_client.headers["Authorization"] = f"Bearer {ALL_PERMISSIONS}"
    return anonymous_client


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
