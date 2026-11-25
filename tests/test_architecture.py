"""Protege la separación por módulos: si alguien la rompe, fallan estos tests."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
MODULES = ROOT / "app" / "modules"

# Qué puede importar cada archivo de OTROS módulos. Lo que no está aquí no puede importar nada.
ALLOWED_FROM_OTHER_MODULES = {
    "router.py": {"public"},
    "dependencies.py": {"public"},
    "schemas.py": {"schemas"},  # los contratos se pueden anidar
    "repository.py": {"models"},  # para cargar relaciones en un mismo query
}
# Las reglas de negocio no dependen de HTTP ni de la base de datos.
BUSINESS_FILES = {"service.py", "directory.py", "ports.py", "exceptions.py"}
TECHNICAL_PACKAGES = {"fastapi", "starlette", "sqlalchemy"}


def python_files(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*.py"))


def runtime_imports(path: Path) -> set[str]:
    """Imports del archivo, sin los de 'if TYPE_CHECKING' (no existen al ejecutar)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    ignored = {
        id(child)
        for node in ast.walk(tree)
        if isinstance(node, ast.If) and ast.unparse(node.test) == "TYPE_CHECKING"
        for child in ast.walk(node)
    }
    names: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in ignored:
            continue
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path}: usa imports absolutos"
            # Se incluye "paquete.nombre" para cubrir "from app.modules.x import service".
            names |= {f"{node.module}.{alias.name}" for alias in node.names}
    return names


def relative_id(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


@pytest.mark.parametrize("path", python_files(MODULES), ids=relative_id)
def test_modules_only_use_the_public_part_of_others(path: Path):
    own_module = path.relative_to(MODULES).parts[0]
    allowed = ALLOWED_FROM_OTHER_MODULES.get(path.name, set())

    for name in runtime_imports(path):
        parts = name.split(".")
        if parts[:2] == ["app", "modules"]:
            assert len(parts) > 3, f"{path.name} importa un módulo entero: {name}"
            assert parts[2] == own_module or parts[3] in allowed, f"import no permitido: {name}"
        elif parts[0] == "app":
            assert parts[1] == "core", f"import no permitido: {name}"


@pytest.mark.parametrize("path", python_files(ROOT / "app" / "core"), ids=relative_id)
def test_core_does_not_know_the_modules(path: Path):
    for name in runtime_imports(path):
        assert not name.startswith("app.") or name.startswith("app.core."), name


@pytest.mark.parametrize(
    "path", [p for p in python_files(MODULES) if p.name in BUSINESS_FILES], ids=relative_id
)
def test_business_rules_do_not_depend_on_http_or_database(path: Path):
    for name in runtime_imports(path):
        assert name.split(".")[0] not in TECHNICAL_PACKAGES, name
        assert ".repository" not in name, name
        assert ".schemas" not in name, name
