# Employee Work Tree API — Spec

## Overview

API REST para gestión de empleados de una empresa. Registra empleados, su historial de puestos (cargo, salario, fechas de inicio/fin) y la jerarquía de jefes y encargados. Construida con **FastAPI + Pydantic v2** siguiendo buenas prácticas.

---

> Documento de diseño inicial. La versión vigente está en [spec.md](../spec.md): las rutas de archivo y los fragmentos de código de aquí son anteriores a la organización por módulos.

---

## Cambios hechos durante la implementación

El código de `app/` es la fuente de verdad. Los fragmentos de este documento son ilustrativos y, donde difieran, vale lo siguiente:

| Tema | Spec original | Implementado | Motivo |
|------|---------------|--------------|--------|
| JWT | `python-jose`, JWKS en caché para siempre | `PyJWT` + `PyJWKClient` | Librería mantenida y soporta la rotación de claves |
| Token ausente | `HTTPBearer` responde por su cuenta | `auto_error=False` + `invalid_token` | Mismo `ErrorResponse` en todos los errores |
| Auth0 caído | No contemplado | `503 auth_provider_unavailable` | No es culpa del token del cliente |
| Commit | `Depends(get_db)` | `Depends(get_db, scope="function")` | Sin esto, el commit ocurre después de enviar la respuesta |
| PATCH | Ignorar los `None` | `exclude_unset=True` | Permite enviar `null` para quitar jefe, departamento o teléfono |
| Import con `TYPE_CHECKING` en schemas | `department.py` | Import normal | Pydantic necesita el tipo en runtime, y no hay ciclo |
| Email | `EmailStr` | `EmailStr` + minúsculas | `EmailStr` solo normaliza el dominio |
| Salario | 2 decimales | Además, máximo 12 dígitos | Coincide con `NUMERIC(12,2)` |
| `/employees/{id}/tree` | `EmployeeDetail` | `EmployeeTreeNode` | `EmployeeDetail` solo tiene un nivel |
| Solapamiento | Solo contra el puesto activo | También contra el último cerrado | Evita solapes al reactivar a un empleado |
| Baja | Libera subordinados | También los departamentos a cargo | Un encargado debe estar activo |
| Concurrencia | No contemplada | Lock de la jerarquía en PostgreSQL | Dos requests simultáneos podían crear un ciclo |
| Handlers HTTP | En `exceptions.py` | `app/api/error_handlers.py` | El dominio no conoce HTTP |
| `get_db` | En `dependencies.py` | `app/database.py` | Junto al engine y la sesión |

---

## Stack

| Capa           | Herramienta                                     |
|----------------|-------------------------------------------------|
| Framework      | FastAPI                                         |
| Contratos      | Pydantic v2                                     |
| Base de datos  | PostgreSQL                                      |
| ORM / Queries  | SQLAlchemy 2.x (async) + asyncpg               |
| Migraciones    | Alembic                                         |
| Testing        | pytest + httpx (AsyncClient) + pytest-asyncio   |
| Python         | 3.12+                                           |

---

## Estructura del proyecto

```
employee-work-tree-api/
├── app/
│   ├── main.py                   # Crea la app, registra routers y exception handlers
│   ├── config.py                 # Settings via pydantic-settings (lee .env)
│   ├── database.py               # Engine async, SessionLocal, get_db()
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py       # APIRouter agregado
│   │       ├── employees.py
│   │       ├── positions.py
│   │       ├── departments.py
│   │       └── job_titles.py
│   ├── schemas/                  # Contratos Pydantic (entrada/salida solamente)
│   │   ├── __init__.py
│   │   ├── common.py             # ErrorResponse, enums compartidos
│   │   ├── employee.py
│   │   ├── position_history.py
│   │   ├── job_title.py
│   │   └── department.py
│   ├── models/                   # Modelos SQLAlchemy (ORM, solo capa de datos)
│   │   ├── __init__.py
│   │   ├── base.py               # DeclarativeBase compartido
│   │   ├── employee.py
│   │   ├── position_history.py
│   │   ├── job_title.py
│   │   └── department.py
│   ├── services/                 # Lógica de negocio (sin conocimiento de HTTP)
│   │   ├── employee_service.py
│   │   ├── position_service.py
│   │   └── job_title_service.py
│   ├── repositories/             # Acceso a datos (queries SQLAlchemy)
│   │   ├── employee_repo.py
│   │   ├── position_repo.py
│   │   └── job_title_repo.py
│   ├── auth/
│   │   ├── auth0.py              # Validación del JWT de Auth0
│   │   └── dependencies.py       # get_current_user(), require_role()
│   ├── dependencies.py           # Inyección: get_db, get_employee_service, etc.
│   └── exceptions.py             # Excepciones de dominio + handlers HTTP
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── conftest.py               # DB de test, fixtures, TestClient
│   ├── test_employees.py
│   ├── test_positions.py
│   ├── test_job_titles.py
│   └── test_departments.py
├── .env.example
├── pyproject.toml
└── spec.md
```

---

## Modelo de datos

### Employee

| Campo         | Tipo PG             | Constraints                              | Descripción                     |
|---------------|---------------------|------------------------------------------|---------------------------------|
| id            | UUID                | PK, default gen_random_uuid()            |                                 |
| first_name    | VARCHAR(80)         | NOT NULL                                 | Nombre(s)                       |
| last_name     | VARCHAR(80)         | NOT NULL                                 | Apellido(s)                     |
| email         | VARCHAR(254)        | NOT NULL, UNIQUE                         | Email único en la empresa       |
| phone         | VARCHAR(20)         | NULLABLE                                 |                                 |
| hire_date     | DATE                | NOT NULL                                 | Fecha de ingreso                |
| is_active     | BOOLEAN             | NOT NULL, default true                   |                                 |
| manager_id    | UUID                | NULLABLE, FK → employees(id)             | Jefe directo (auto-referencia)  |
| department_id | UUID                | NULLABLE, FK → departments(id)           |                                 |
| created_at    | TIMESTAMPTZ         | NOT NULL, default now()                  |                                 |
| updated_at    | TIMESTAMPTZ         | NOT NULL, default now()                  |                                 |

### JobTitle

Catálogo centralizado de puestos disponibles en la empresa. `PositionHistory` solo puede referenciar títulos de esta tabla.

| Campo       | Tipo PG        | Constraints                   | Descripción                                      |
|-------------|----------------|-------------------------------|--------------------------------------------------|
| id          | UUID           | PK, default gen_random_uuid() |                                                  |
| name        | VARCHAR(120)   | NOT NULL, UNIQUE              | e.g. "Senior Developer", "HR Manager"            |
| description | TEXT           | NULLABLE                      | Descripción de responsabilidades del puesto      |
| is_active   | BOOLEAN        | NOT NULL, default true        | `false` = puesto descontinuado (no asignable)    |
| created_at  | TIMESTAMPTZ    | NOT NULL, default now()       |                                                  |
| updated_at  | TIMESTAMPTZ    | NOT NULL, default now()       |                                                  |

### PositionHistory

| Campo        | Tipo PG        | Constraints                              | Descripción                           |
|--------------|----------------|------------------------------------------|---------------------------------------|
| id           | UUID           | PK, default gen_random_uuid()            |                                       |
| employee_id  | UUID           | NOT NULL, FK → employees(id)             |                                       |
| job_title_id | UUID           | NOT NULL, FK → job_titles(id)            | Referencia al catálogo de puestos     |
| salary       | NUMERIC(12, 2) | NOT NULL, CHECK > 0                      | Salario (2 decimales, sin float)      |
| start_date   | DATE           | NOT NULL                                 |                                       |
| end_date     | DATE           | NULLABLE                                 | NULL = puesto activo actualmente      |
| notes        | TEXT           | NULLABLE                                 | Motivo del cambio / promoción         |
| created_at   | TIMESTAMPTZ    | NOT NULL, default now()                  |                                       |

Constraints en DB:
- `UNIQUE (employee_id) WHERE end_date IS NULL` → un único puesto activo por empleado.
- `UNIQUE (employee_id, start_date)` → previene duplicados en reintentos (idempotencia).
- FK a `job_titles` impide asignar un título que no exista en el catálogo.

### Department

| Campo         | Tipo PG             | Constraints                              | Descripción                           |
|---------------|---------------------|------------------------------------------|---------------------------------------|
| id            | UUID                | PK, default gen_random_uuid()            |                                       |
| name          | VARCHAR(100)        | NOT NULL, UNIQUE                         |                                       |
| manager_id    | UUID                | NULLABLE, FK → employees(id)             | Encargado del departamento            |
| created_at    | TIMESTAMPTZ         | NOT NULL, default now()                  |                                       |

---

## Contratos Pydantic

Regla: **nunca exponer el modelo ORM directamente**. Cada operación tiene su propio schema.

### `app/schemas/common.py`

```python
# from __future__ import annotations permite usar tipos como str | None
# en Python 3.9 sin importar Union. En 3.10+ ya es nativo, pero es buena práctica.
from __future__ import annotations
from typing import Any
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    # Todos los errores de la API tienen esta forma.
    # El cliente puede distinguir errores por el campo "error" (snake_case)
    # sin tener que parsear el mensaje de texto.
    error:   str          # código de máquina, e.g. "employee_not_found"
    message: str          # descripción legible para el usuario
    details: Any | None = None  # info extra opcional (p.ej. campos inválidos)
```

---

### `app/schemas/job_title.py`

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class JobTitleCreate(BaseModel):
    # Annotated[str, Field(...)] es la forma de Pydantic v2 para combinar
    # el tipo con sus validaciones en un solo lugar, sin romper los type checkers.
    name:        Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str | None, Field(max_length=1000)] = None

    # extra="forbid" hace que Pydantic rechace cualquier campo no declarado.
    # Si el cliente manda {"name": "...", "typo_field": "..."}, devuelve 422.
    # Esto detecta errores de escritura en el cliente antes de llegar a la DB.
    model_config = ConfigDict(extra="forbid")


class JobTitleUpdate(BaseModel):
    # En un PATCH todos los campos son opcionales (= None por defecto).
    # El servicio ignorará los campos que lleguen como None y solo actualizará
    # los que traigan un valor real.
    name:        Annotated[str | None, Field(min_length=1, max_length=120)] = None
    description: Annotated[str | None, Field(max_length=1000)] = None
    is_active:   bool | None = None

    model_config = ConfigDict(extra="forbid")


class JobTitleResponse(BaseModel):
    id:          UUID
    name:        str
    description: str | None
    is_active:   bool
    created_at:  datetime
    updated_at:  datetime

    # from_attributes=True permite que Pydantic lea atributos de un objeto ORM
    # directamente, sin necesidad de convertirlo a dict primero.
    # FastAPI llama a model_validate(orm_object) internamente cuando se lo pedimos.
    model_config = ConfigDict(from_attributes=True)
```

---

### `app/schemas/position_history.py`

```python
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Importamos el schema de respuesta de JobTitle para embeber el objeto completo
# en la respuesta. El cliente recibe el nombre del puesto sin hacer un segundo request.
from app.schemas.job_title import JobTitleResponse


class PositionCreate(BaseModel):
    """Asignar un nuevo puesto a un empleado. job_title_id debe existir en el catálogo."""

    # El cliente manda el UUID del puesto del catálogo, no el nombre como texto libre.
    # Si el UUID no existe, el servicio lanza job_title_not_found antes de insertar.
    job_title_id: UUID

    # Decimal evita errores de punto flotante. Con float, 10.1 + 0.2 ≠ 10.3 en binario.
    # gt=Decimal("0") rechaza salarios negativos o cero en la validación de Pydantic,
    # antes de llegar al CHECK constraint de la DB.
    salary:       Annotated[Decimal, Field(gt=Decimal("0"), decimal_places=2)]
    start_date:   date
    notes:        Annotated[str | None, Field(max_length=500)] = None

    model_config = ConfigDict(extra="forbid")

    # model_validator(mode="after") se ejecuta después de que todos los campos
    # individuales ya fueron validados. Aquí podemos acceder a self.start_date
    # como un objeto date real, no como string crudo.
    @model_validator(mode="after")
    def start_date_not_in_future(self) -> "PositionCreate":
        if self.start_date > date.today():
            # Lanzar ValueError dentro de un validator hace que Pydantic lo
            # convierta en un error de validación estándar (HTTP 422).
            raise ValueError("start_date no puede ser una fecha futura")
        return self


class PositionSummary(BaseModel):
    """Puesto activo embebido dentro de EmployeeResponse.
    Solo expone los campos necesarios para un resumen; sin id ni employee_id."""
    job_title:  JobTitleResponse   # objeto completo del catálogo
    salary:     Decimal
    start_date: date

    model_config = ConfigDict(from_attributes=True)


class PositionHistoryResponse(BaseModel):
    """Respuesta completa de una fila del historial de puestos."""
    id:           UUID
    employee_id:  UUID
    # Pydantic navega la relación ORM job_title → JobTitle automáticamente
    # gracias a from_attributes=True. SQLAlchemy debe tener la relación definida.
    job_title:    JobTitleResponse
    salary:       Decimal
    start_date:   date
    end_date:     date | None      # None significa que este es el puesto actual
    notes:        str | None
    created_at:   datetime

    model_config = ConfigDict(from_attributes=True)
```

---

### `app/schemas/department.py`

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID
from typing import Annotated, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

# TYPE_CHECKING es True solo cuando un type checker (mypy, pyright) analiza el código,
# nunca en runtime. Usamos esto para importar EmployeeResponse sin crear un import
# circular real entre department.py y employee.py.
# En runtime, la anotación "EmployeeResponse" (como string) se resuelve de forma lazy.
if TYPE_CHECKING:
    from app.schemas.employee import EmployeeResponse


class DepartmentCreate(BaseModel):
    name:       Annotated[str, Field(min_length=1, max_length=100)]
    manager_id: UUID | None = None

    model_config = ConfigDict(extra="forbid")


class DepartmentUpdate(BaseModel):
    # Separamos Create de Update aunque los campos sean similares porque
    # en el futuro pueden divergir. Update tiene todos opcionales; Create no.
    name:       Annotated[str | None, Field(min_length=1, max_length=100)] = None
    manager_id: UUID | None = None

    model_config = ConfigDict(extra="forbid")


class DepartmentResponse(BaseModel):
    id:         UUID
    name:       str
    manager_id: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DepartmentDetail(DepartmentResponse):
    """Departamento con sus empleados activos — usado solo en GET /departments/{id}."""

    # list["EmployeeResponse"] con string forward reference porque el import
    # real está bajo TYPE_CHECKING. Pydantic resuelve el string en runtime
    # gracias a model_rebuild() o update_forward_refs().
    employees: list["EmployeeResponse"] = []

    model_config = ConfigDict(from_attributes=True)
```

---

### `app/schemas/employee.py`

```python
from __future__ import annotations
from datetime import date, datetime
from uuid import UUID
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

# EmailStr es un tipo especial de Pydantic que valida formato de email.
# Requiere el extra "email-validator": pip install pydantic[email]
from app.schemas.position_history import PositionSummary, PositionHistoryResponse


class EmployeeCreate(BaseModel):
    """Contrato de entrada para crear un empleado.
    Solo contiene los campos que el cliente puede enviar al momento del registro."""

    first_name:    Annotated[str, Field(min_length=1, max_length=80)]
    last_name:     Annotated[str, Field(min_length=1, max_length=80)]
    # EmailStr valida formato (usuario@dominio.ext) y normaliza a minúsculas.
    email:         EmailStr
    phone:         Annotated[str | None, Field(max_length=20)] = None
    hire_date:     date
    # Campos opcionales: se pueden asignar después con PATCH
    manager_id:    UUID | None = None
    department_id: UUID | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def hire_date_not_in_future(self) -> "EmployeeCreate":
        if self.hire_date > date.today():
            raise ValueError("hire_date no puede ser una fecha futura")
        return self


class EmployeeUpdate(BaseModel):
    """Contrato de entrada para PATCH. Todos los campos opcionales.
    El servicio aplica solo los campos que no sean None."""

    first_name:    Annotated[str | None, Field(min_length=1, max_length=80)] = None
    last_name:     Annotated[str | None, Field(min_length=1, max_length=80)] = None
    phone:         Annotated[str | None, Field(max_length=20)] = None
    manager_id:    UUID | None = None
    department_id: UUID | None = None
    # is_active se expone aquí para permitir reactivar un empleado dado de baja
    is_active:     bool | None = None

    model_config = ConfigDict(extra="forbid")


class EmployeeResponse(BaseModel):
    """Contrato de salida para listas y respuestas de escritura (POST/PATCH).
    Incluye el puesto activo como resumen para evitar un segundo request al cliente."""

    id:               UUID
    first_name:       str
    last_name:        str
    email:            EmailStr
    phone:            str | None
    hire_date:        date
    is_active:        bool
    manager_id:       UUID | None
    department_id:    UUID | None
    # None si el empleado aún no tiene puesto asignado en position_history
    current_position: PositionSummary | None
    created_at:       datetime
    updated_at:       datetime

    # from_attributes=True permite construir este schema desde un objeto ORM.
    # Pydantic accederá a employee.current_position navegando la relación SQLAlchemy.
    model_config = ConfigDict(from_attributes=True)


class EmployeeDetail(EmployeeResponse):
    """Contrato de salida extendido — usado solo en GET /employees/{id}.
    Hereda todos los campos de EmployeeResponse y agrega los que son costosos de cargar."""

    # Historial completo de puestos, ordenado del más reciente al más antiguo
    position_history: list[PositionHistoryResponse] = []
    # Empleados que tienen a este como manager_id (un nivel de profundidad)
    direct_reports:   list[EmployeeResponse] = []

    model_config = ConfigDict(from_attributes=True)
```

---

## Endpoints

Base path: `/api/v1`

### Employees

| Método | Ruta                       | Body             | Respuesta                    | Status | Descripción                               |
|--------|----------------------------|------------------|------------------------------|--------|-------------------------------------------|
| GET    | `/employees`               | —                | `list[EmployeeResponse]`     | 200    | Lista empleados (activos por defecto)      |
| GET    | `/employees/{id}`          | —                | `EmployeeDetail`             | 200    | Empleado con historial y reportes          |
| POST   | `/employees`               | `EmployeeCreate` | `EmployeeResponse`           | 201    | Registra un nuevo empleado                 |
| PATCH  | `/employees/{id}`          | `EmployeeUpdate` | `EmployeeResponse`           | 200    | Actualiza datos del empleado               |
| DELETE | `/employees/{id}`          | —                | —                            | 204    | Da de baja (soft delete)                  |
| GET    | `/employees/{id}/reports`  | —                | `list[EmployeeResponse]`     | 200    | Reportes directos (un nivel)               |
| GET    | `/employees/{id}/tree`     | —                | `EmployeeTreeNode`           | 200    | Árbol completo de reportes (recursivo)     |

Query params en `GET /employees`:

| Param       | Tipo    | Default | Descripción                         |
|-------------|---------|---------|-------------------------------------|
| `is_active` | bool    | `true`  | Filtrar por estado activo/inactivo  |
| `email`     | email   | —       | Buscar por email exacto             |

### Position History

| Método | Ruta                                 | Body             | Respuesta                       | Status | Descripción                            |
|--------|--------------------------------------|------------------|---------------------------------|--------|----------------------------------------|
| GET    | `/employees/{id}/positions`          | —                | `list[PositionHistoryResponse]` | 200    | Historial completo ordenado por fecha  |
| GET    | `/employees/{id}/positions/current`  | —                | `PositionHistoryResponse`       | 200    | Puesto activo (`end_date IS NULL`)     |
| POST   | `/employees/{id}/positions`          | `PositionCreate` | `PositionHistoryResponse`       | 201    | Asigna nuevo puesto, cierra el anterior|

### Job Titles (catálogo)

| Método | Ruta                | Body               | Respuesta                  | Status | Descripción                               |
|--------|---------------------|--------------------|----------------------------|--------|-------------------------------------------|
| GET    | `/job-titles`       | —                  | `list[JobTitleResponse]`   | 200    | Lista puestos (activos por defecto)        |
| GET    | `/job-titles/{id}`  | —                  | `JobTitleResponse`         | 200    | Detalle de un puesto                       |
| POST   | `/job-titles`       | `JobTitleCreate`   | `JobTitleResponse`         | 201    | Crea un nuevo puesto en el catálogo        |
| PATCH  | `/job-titles/{id}`  | `JobTitleUpdate`   | `JobTitleResponse`         | 200    | Edita nombre, descripción o lo desactiva   |

Query params en `GET /job-titles`:

| Param       | Tipo | Default | Descripción                              |
|-------------|------|---------|------------------------------------------|
| `is_active` | bool | `true`  | Filtrar por puestos activos/inactivos    |

> Un `JobTitle` con `is_active = false` no puede asignarse en nuevos puestos (`409 job_title_inactive`), pero las asignaciones históricas existentes se conservan.

### Departments

| Método | Ruta                   | Body               | Respuesta                   | Status | Descripción                     |
|--------|------------------------|--------------------|-----------------------------|--------|---------------------------------|
| GET    | `/departments`         | —                  | `list[DepartmentResponse]`  | 200    | Lista todos los departamentos   |
| GET    | `/departments/{id}`    | —                  | `DepartmentDetail`          | 200    | Depto con sus empleados activos |
| POST   | `/departments`         | `DepartmentCreate` | `DepartmentResponse`        | 201    | Crea departamento               |
| PATCH  | `/departments/{id}`    | `DepartmentUpdate` | `DepartmentResponse`        | 200    | Renombra o cambia encargado     |

---

## Reglas de negocio

### Asignar nuevo puesto (`POST /employees/{id}/positions`)
1. Se busca el puesto actual (`end_date IS NULL`).
2. Si existe, se cierra: `end_date = new_start_date - 1 day`.
3. Se inserta el nuevo registro con `end_date = NULL`.
4. Si `start_date` del nuevo puesto ≤ `start_date` del puesto actual → `409 overlapping_position`.

### Jerarquía de jefes
- Un empleado tiene un único `manager_id` (jefe directo).
- El `manager_id` debe apuntar a un empleado `is_active = true`.
- El `department.manager_id` debe apuntar a un empleado `is_active = true`.
- Antes de asignar `manager_id` el servicio recorre la cadena de ascendentes para detectar ciclos.

### Baja de empleado (`DELETE /employees/{id}`)
- Soft delete: `is_active = false`, `updated_at = now()`.
- Se cierra el puesto activo: `end_date = today`.
- Los empleados y departamentos que tenían a este como `manager_id` quedan con `manager_id = NULL`.

---

## Manejo de errores

Todas las respuestas de error usan `ErrorResponse`. Los handlers se registran en `main.py`.

| HTTP | `error`                      | Cuándo                                                       |
|------|------------------------------|--------------------------------------------------------------|
| 401  | `invalid_token`              | JWT ausente, expirado, firma inválida o audience incorrecto  |
| 403  | `insufficient_permissions`   | Token válido pero sin el permiso requerido                   |
| 404  | `employee_not_found`         | UUID no existe en employees                                  |
| 404  | `department_not_found`       | UUID no existe en departments                                |
| 404  | `job_title_not_found`        | UUID no existe en job_titles                                 |
| 404  | `no_active_position`         | Empleado no tiene puesto activo                              |
| 409  | `email_already_exists`       | Email duplicado                                              |
| 409  | `overlapping_position`       | Fechas de puestos se solapan                                 |
| 409  | `circular_manager_reference` | Asignar manager_id crearía un ciclo jerárquico               |
| 409  | `inactive_manager`           | El manager_id apunta a un empleado inactivo                  |
| 409  | `job_title_inactive`         | El job_title_id apunta a un puesto descontinuado             |
| 409  | `job_title_name_exists`      | Ya existe un JobTitle con ese nombre                         |
| 409  | `department_name_exists`     | Ya existe un departamento con ese nombre                     |
| 409  | `employee_inactive`          | Asignar un puesto a un empleado dado de baja                 |
| 422  | `validation_error`           | Pydantic rechaza el body (automático por FastAPI)            |
| 503  | `auth_provider_unavailable`  | No se pudo contactar a Auth0                                 |

---

## Desacoplamiento

El proyecto sigue una arquitectura de capas estricta. Cada capa **solo habla con la capa inmediatamente inferior** y nunca salta niveles.

```
HTTP Request
     │
     ▼
┌─────────────┐   schemas/      Valida y tipea el body de entrada y salida.
│   Router    │ ◀────────────── Nunca contiene lógica de negocio.
│  (api/v1/)  │                 Solo llama al servicio y devuelve la respuesta.
└──────┬──────┘
       │ llama a
       ▼
┌─────────────┐                 Contiene las reglas de negocio puras.
│   Service   │                 No sabe nada de HTTP (sin Request, sin Response).
│ (services/) │                 No hace queries SQL directamente.
└──────┬──────┘
       │ llama a
       ▼
┌─────────────┐                 Solo hace queries a la DB (SELECT, INSERT, UPDATE).
│ Repository  │                 No tiene reglas de negocio.
│(repositories│                 Recibe y devuelve modelos ORM o tipos primitivos.
└──────┬──────┘
       │
       ▼
  PostgreSQL
```

### Por qué importa esta separación

| Sin separación | Con separación |
|----------------|----------------|
| Cambiar PostgreSQL por otro motor rompe el router | El router nunca habla con la DB; solo el repo cambia |
| Testear el servicio requiere levantar HTTP | El servicio se testea con un repo mock, sin servidor |
| La lógica de negocio está dispersa en los endpoints | Toda la lógica está en un lugar; fácil de leer y cambiar |

### Regla de dependencias

```
Router  →  Service  →  Repository  →  DB
  ↑            ↑              ↑
  │            │              │
schemas/    exceptions/    models/
```

- El router **importa** `schemas` y `services`. No importa `repositories` ni `models`.
- El service **importa** `repositories` y `exceptions`. No importa `schemas` de FastAPI.
- El repository **importa** `models`. No importa `schemas` ni `services`.

### Inyección de dependencias en FastAPI

FastAPI resuelve las dependencias automáticamente. El router declara qué necesita con `Depends()` y FastAPI se encarga de construirlo.

```python
# dependencies.py — fábrica centralizada de servicios
# Aquí se "cablea" qué repositorio usa cada servicio.
# Si mañana cambiamos el repo por uno en memoria para tests, solo cambiamos aquí.

async def get_employee_service(
    db: AsyncSession = Depends(get_db),         # FastAPI inyecta la sesión de DB
) -> EmployeeService:
    repo = EmployeeRepository(db)               # el repo recibe la sesión
    return EmployeeService(repo)                # el servicio recibe el repo
```

```python
# router — el endpoint solo declara qué necesita, no cómo construirlo
@router.get("/{employee_id}", response_model=EmployeeDetail)
async def get_employee(
    employee_id: UUID,
    service: EmployeeService = Depends(get_employee_service),  # FastAPI lo construye
):
    return await service.get_by_id(employee_id)
```

### Protocolo de interfaces (opcional avanzado)

Para máximo desacoplamiento, los servicios pueden depender de un `Protocol` en lugar de la clase concreta del repositorio. Esto permite intercambiar la implementación sin modificar el servicio:

```python
# services/protocols.py
from typing import Protocol
from uuid import UUID
from app.models.employee import Employee


class IEmployeeRepository(Protocol):
    async def get_by_id(self, id: UUID) -> Employee | None: ...
    async def get_by_email(self, email: str) -> Employee | None: ...
    async def save(self, employee: Employee) -> Employee: ...
    async def delete(self, id: UUID) -> None: ...
```

```python
# El servicio depende del protocolo, no de la clase concreta
class EmployeeService:
    def __init__(self, repo: IEmployeeRepository) -> None:
        self._repo = repo
    # En tests se puede pasar un mock que cumpla el Protocol
    # sin necesidad de una DB real
```

---

## Decisiones de diseño

| Decisión | Elección | Razón |
|----------|----------|-------|
| Arquitectura en capas Router→Service→Repository | Estricta, sin saltos | Cada capa es testeable de forma independiente |
| Schemas separados por operación | `Create` / `Update` / `Response` / `Detail` | Nunca exponer campos internos; evolución independiente por operación |
| `extra="forbid"` en entradas | Sí | Detecta typos del cliente inmediatamente, no silenciosamente |
| `from_attributes=True` en salidas | Sí | Serializa el ORM model directamente sin mapeo manual |
| Salario | `NUMERIC(12,2)` / `Decimal` | Evita errores de punto flotante en operaciones monetarias |
| Partial update | PATCH con todos opcionales | Permite actualizar un solo campo sin enviar el recurso completo |
| Unique constraint `end_date IS NULL` | Partial index en PostgreSQL | La DB garantiza un único puesto activo por empleado, no solo el código |
| Timestamps | `TIMESTAMPTZ` | Almacena zona horaria; evita bugs en entornos multi-zona |
| IDs | UUID v4 | Evita enumeración; portable entre entornos y sin colisiones en imports |
| Baja | Soft delete | Los registros históricos deben conservarse para auditoría |
| Dependencias con `Depends()` | Centralizado en `dependencies.py` | Un solo lugar para "cablear" servicios; fácil de sustituir en tests |

---

## Variables de entorno (`.env.example`)

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/employee_db
DATABASE_URL_TEST=postgresql+asyncpg://user:password@localhost:5432/employee_db_test
```

---

## Autenticación y Autorización (Auth0)

### Flujo

```
Cliente                   Auth0                     FastAPI
  │                          │                          │
  │── POST /oauth/token ────▶│                          │
  │◀─ access_token (JWT) ───│                          │
  │                          │                          │
  │── GET /api/v1/employees ─────────────────────────▶│
  │   Authorization: Bearer <JWT>                       │
  │                          │                          │
  │                          │◀── validar JWT (JWKS) ──│
  │                          │─── claims ok ──────────▶│
  │◀─ 200 OK ───────────────────────────────────────────│
```

La API **nunca maneja passwords**. Auth0 emite el JWT; FastAPI solo lo valida contra las claves públicas de Auth0 (JWKS).

### Dependencias

```toml
python-jose[cryptography] = "^3.3"   # decodifica y valida JWT RS256
httpx                                 # descarga JWKS en startup
```

### `app/auth/auth0.py`

```python
from __future__ import annotations
import httpx
from jose import jwt, JWTError
from app.config import settings
from app.exceptions import InvalidTokenError


# Cache en memoria del JSON Web Key Set (JWKS) de Auth0.
# Auth0 publica sus claves públicas en una URL estándar. Las descargamos una vez
# y las guardamos en memoria para no hacer HTTP en cada request.
# En producción con múltiples workers, cada worker tendrá su propia copia (aceptable).
_jwks_cache: dict | None = None


async def get_jwks() -> dict:
    """Descarga las claves públicas de Auth0 la primera vez; luego usa caché."""
    global _jwks_cache
    if _jwks_cache is None:
        # httpx es el cliente HTTP async recomendado con FastAPI.
        # Usamos context manager para cerrar la conexión al terminar.
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
            )
            # raise_for_status() lanza una excepción si el status HTTP >= 400
            resp.raise_for_status()
            _jwks_cache = resp.json()
    return _jwks_cache


async def decode_token(token: str) -> dict:
    """Valida la firma del JWT y retorna sus claims si es válido."""
    jwks = await get_jwks()
    try:
        # jwt.decode verifica:
        #   1. La firma con las claves públicas del JWKS
        #   2. Que el algoritmo sea RS256 (asimétrico: Auth0 firma, nosotros verificamos)
        #   3. Que "aud" en el token coincida con AUTH0_AUDIENCE (nuestra API)
        #   4. Que "iss" sea el tenant de Auth0 correcto
        #   5. Que el token no haya expirado (claim "exp")
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.AUTH0_AUDIENCE,
            issuer=f"https://{settings.AUTH0_DOMAIN}/",
        )
    except JWTError as exc:
        # Convertimos el error de la librería a nuestra excepción de dominio.
        # Así el handler en main.py lo mapea a HTTP 401 con nuestro ErrorResponse.
        raise InvalidTokenError(str(exc)) from exc
    return payload
```

### `app/auth/dependencies.py`

```python
from __future__ import annotations
from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.auth0 import decode_token
from app.schemas.common import TokenPayload
from app.exceptions import InvalidTokenError, InsufficientPermissionsError

# HTTPBearer extrae el token del header "Authorization: Bearer <token>".
# Si el header está ausente o mal formado, FastAPI responde 403 automáticamente
# antes de llegar a nuestro código.
bearer_scheme = HTTPBearer()


async def get_current_user(
    # Security() es como Depends() pero le indica a FastAPI que registre
    # este esquema en la documentación OpenAPI (candado en Swagger UI).
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> TokenPayload:
    # credentials.credentials es el string del token sin el prefijo "Bearer "
    payload = await decode_token(credentials.credentials)
    return TokenPayload(
        sub=payload["sub"],
        email=payload.get("email"),
        # Auth0 incluye los permisos en el claim "permissions" cuando se configura
        # en la sección "API Permissions" del dashboard de Auth0.
        permissions=payload.get("permissions", []),
    )


def require_permission(permission: str):
    """Factory de dependencies: genera una función que valida un permiso concreto.

    Uso: Depends(require_permission("employees:write"))

    Por qué una factory y no un decorador:
    - Cada endpoint necesita un permiso diferente.
    - La factory devuelve una dependency nueva para cada permiso sin duplicar código.
    """
    async def _check(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
        if permission not in user.permissions:
            # Esta excepción es de dominio; el handler en main.py la convierte a 403.
            raise InsufficientPermissionsError(required=permission)
        return user
    return _check
```

### `app/schemas/common.py` (ampliado)

```python
from __future__ import annotations
from typing import Any
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error:   str
    message: str
    details: Any | None = None


class TokenPayload(BaseModel):
    """Claims del JWT que nos interesan. No guardamos el token completo, solo lo que usamos."""
    sub:         str              # "subject": ID único del usuario en Auth0 (p.ej. "auth0|abc123")
    email:       str | None       # claim opcional; activarlo en Auth0 Actions si se necesita
    permissions: list[str] = []   # lista de permisos asignados al usuario en esta API
```

### Permisos definidos en Auth0

| Permiso                  | Quién lo tiene          | Qué permite                                   |
|--------------------------|-------------------------|-----------------------------------------------|
| `employees:read`         | HR, managers, admins    | GET en employees, positions, departments      |
| `employees:write`        | HR, admins              | POST / PATCH / DELETE en employees            |
| `positions:write`        | HR, admins              | POST en positions (asignar puestos)           |
| `job-titles:write`       | Admins                  | POST / PATCH en job-titles                    |
| `departments:write`      | Admins                  | POST / PATCH en departments                   |

### Uso en los routers

```python
from app.auth.dependencies import require_permission

# prefix agrupa todos los endpoints bajo /employees automáticamente.
# tags agrupa los endpoints en la documentación Swagger UI.
router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("/", response_model=list[EmployeeResponse])
async def list_employees(
    # FastAPI resuelve require_permission("employees:read") como una dependency.
    # Si el token no tiene ese permiso, el request se rechaza antes de entrar al handler.
    user: TokenPayload = Depends(require_permission("employees:read")),
    service: EmployeeService = Depends(get_employee_service),
):
    # El router no sabe nada de DB ni de lógica de negocio.
    # Solo delega al servicio y retorna el resultado.
    return await service.list_active()


@router.post("/", response_model=EmployeeResponse, status_code=201)
async def create_employee(
    # FastAPI parsea y valida el body contra EmployeeCreate automáticamente.
    # Si falla la validación, responde 422 sin llegar al handler.
    body: EmployeeCreate,
    user: TokenPayload = Depends(require_permission("employees:write")),
    service: EmployeeService = Depends(get_employee_service),
):
    return await service.create(body)
```

### Variables de entorno adicionales

```env
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_AUDIENCE=https://employee-api        # API Identifier configurado en Auth0
```

### Errores de autenticación

| HTTP | `error`                   | Cuándo                                               |
|------|---------------------------|------------------------------------------------------|
| 401  | `invalid_token`           | JWT ausente, expirado, firma inválida o audience incorrecto |
| 403  | `insufficient_permissions`| Token válido pero sin el permiso requerido           |

---

## Idempotencia

La idempotencia garantiza que ejecutar la misma operación más de una vez produce el mismo resultado. Crítico cuando el cliente reintenta por timeout o error de red.

### Análisis por endpoint

| Método | Ruta                              | ¿Idempotente? | Notas                                                                               |
|--------|-----------------------------------|---------------|-------------------------------------------------------------------------------------|
| GET    | cualquiera                        | ✅ Sí         | Sin efectos secundarios por definición.                                             |
| DELETE | `/employees/{id}`                 | ✅ Sí         | Soft delete: si ya está inactivo, responde `204` sin error (verificar antes de actuar). |
| PATCH  | `/employees/{id}`                 | ✅ Sí         | Reenviar el mismo body produce el mismo estado; sin contador ni timestamp cambia.    |
| POST   | `/employees`                      | ⚠️ No natural | Email tiene `UNIQUE` en DB → segundo intento devuelve `409 email_already_exists`. El cliente debe tratar `409` como "ya existe" y hacer GET para recuperar el recurso. |
| POST   | `/employees/{id}/positions`       | ⚠️ No natural | Dos POST con los mismos datos crearían dos registros. Mitigación: constraint `UNIQUE (employee_id, start_date)` en `position_history` → el segundo intento devuelve `409 overlapping_position`. |
| POST   | `/departments`                    | ⚠️ No natural | `UNIQUE (name)` en DB → segundo intento devuelve `409`. Mismo patrón que employees. |

### Patrón de mitigación para POST

Para los endpoints que crean recursos, el cliente debe seguir este patrón:

```
1. POST /employees  →  201 Created          (primer intento: OK)
2. POST /employees  →  409 email_already_exists  (reintento: recurso ya existe)
   └─ cliente hace GET /employees?email=x   →  200  (recupera el recurso existente)
```

La API nunca crea duplicados silenciosos. El `409` es la señal de "ya existe, búscalo".

### Constraint adicional en DB para posiciones

```sql
-- Garantiza que no haya dos posiciones con la misma fecha de inicio para el mismo empleado
ALTER TABLE position_history
  ADD CONSTRAINT uq_employee_start_date UNIQUE (employee_id, start_date);
```

Esto hace que `POST /employees/{id}/positions` sea seguro ante reintentos: el segundo intento falla en DB con `UniqueViolationError`, que el handler mapea a `409 overlapping_position`.

---

## Connection Pool (PostgreSQL + asyncpg)

### Configuración en `app/database.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,          # conexiones persistentes en el pool
    max_overflow=5,        # conexiones extra permitidas cuando el pool está lleno
    pool_timeout=30,       # segundos a esperar por una conexión antes de error
    pool_recycle=1800,     # recicla conexiones después de 30 min (evita "connection gone")
    pool_pre_ping=True,    # verifica que la conexión siga viva antes de usarla
    echo=settings.DEBUG,   # loguea SQL solo en desarrollo
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,   # evita lazy-load tras commit en contexto async
    autocommit=False,
    autoflush=False,
)
```

### Parámetros explicados

| Parámetro        | Valor | Por qué                                                                     |
|------------------|-------|-----------------------------------------------------------------------------|
| `pool_size`      | 10    | Número base de conexiones mantenidas abiertas. Es por worker. |
| `max_overflow`   | 5     | Permite picos puntuales sin rechazar requests. Total máximo = 15 por worker.           |
| `pool_timeout`   | 30 s  | Si en 30 s no hay conexión disponible, lanza `TimeoutError` (mejor que esperar infinito). |
| `pool_recycle`   | 1800 s| PostgreSQL cierra conexiones idle después de `tcp_keepalives_idle`. Reciclar antes previene `connection reset`. |
| `pool_pre_ping`  | True  | Envía `SELECT 1` antes de cada uso. Detecta conexiones muertas sin llegar al handler. |
| `expire_on_commit`| False| En async, acceder a atributos después del `commit` no dispara un nuevo query (ya no hay sesión activa). |

### Dependency en `app/dependencies.py`

```python
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    # AsyncSessionLocal() abre una sesión desde el pool.
    # El context manager (async with) garantiza que la sesión se cierre
    # y la conexión regrese al pool al finalizar, incluso si hay una excepción.
    async with AsyncSessionLocal() as session:
        try:
            # "yield" convierte esta función en un generador.
            # FastAPI inyecta la sesión en el endpoint, ejecuta el handler,
            # y luego retoma la ejecución aquí (después del yield).
            yield session
            # El commit solo ocurre si el handler terminó sin excepciones.
            # La sesión acumula todos los cambios del request; se persisten en un único commit.
            await session.commit()
        except Exception:
            # Si algo falló (en el handler o en el commit), deshacemos todo.
            # Esto garantiza que la DB no quede en un estado parcial.
            await session.rollback()
            raise  # re-lanzamos para que el handler de errores de FastAPI lo capture
```

El `commit` vive en la dependency, no en el servicio. Esto separa responsabilidades:
- El **servicio** no sabe cuándo se hace commit (puede ser parte de una transacción más grande).
- El **router** no sabe nada de transacciones.
- La **dependency** es el único lugar que decide cuándo persistir o revertir.

### Tamaño del pool vs. workers

```
El pool es POR WORKER (cada proceso tiene el suyo):
  conexiones máximas = workers × (pool_size + max_overflow)

Ejemplo — 4 workers, pool_size = 10, max_overflow = 5:
  4 × 15 = 60 conexiones hacia PostgreSQL
```

PostgreSQL por defecto acepta 100 conexiones (`max_connections`). Con PgBouncer en modo transaction pooling se puede reducir `pool_size` a 2-3 y escalar a muchos más workers.

### Variables de entorno relevantes

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/employee_db
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=5
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=1800
```

---

## Scope excluido

- Paginación
- Multi-moneda en salarios
- Roles y permisos por departamento
- Eventos / auditoría de cambios (audit log)
- PgBouncer / connection pooler externo
