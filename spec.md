# Employee Work Tree API — Spec

API REST para gestionar los empleados de una empresa: sus datos, el historial de puestos (salario y fechas), los departamentos y la jerarquía de jefes. Es un proyecto de práctica de FastAPI.

Las instrucciones de uso están en el [README](README.md). El documento de diseño inicial se conserva en [docs/spec-original.md](docs/spec-original.md); donde difiera, vale este y el código.

## Módulos

| Módulo | Responsabilidad | Spec |
|---|---|---|
| `employees` | Empleados, jerarquía y organigrama | [spec](app/modules/employees/spec.md) |
| `positions` | Historial de puestos, salarios y fechas | [spec](app/modules/positions/spec.md) |
| `job_titles` | Catálogo de puestos | [spec](app/modules/job_titles/spec.md) |
| `departments` | Departamentos y encargados | [spec](app/modules/departments/spec.md) |
| `auth` | Autenticación y permisos | [spec](app/modules/auth/spec.md) |
| `core` | Piezas técnicas comunes | [spec](app/core/spec.md) |

## Estructura

```
app/
├── main.py              # crea la aplicación
├── router.py            # reúne los routers bajo /api/v1
├── models.py            # registro de modelos para Alembic
├── core/                # técnico y común: config, base de datos, errores
├── modules/
│   ├── auth/
│   ├── employees/
│   ├── positions/
│   ├── departments/
│   └── job_titles/
└── seed/                # datos de ejemplo
alembic/                 # migraciones
tests/                   # una carpeta por módulo
```

Los cuatro módulos de negocio tienen los mismos archivos:

| Archivo | Responsabilidad |
|---|---|
| `router.py` | Endpoints HTTP; sin reglas de negocio |
| `schemas.py` | Contratos de entrada y salida (Pydantic) |
| `service.py` | Reglas de negocio |
| `ports.py` | Lo que el servicio necesita de fuera (`Protocol`) |
| `repository.py` | Consultas a la base de datos |
| `models.py` | Tablas (SQLAlchemy) |
| `exceptions.py` | Errores del módulo |
| `dependencies.py` | Conecta los puertos con sus implementaciones |
| `public.py` | Lo único que otros módulos pueden usar |

`employees` tiene además `directory.py`, con las comprobaciones que ofrece a los demás.

## Reglas de desacoplamiento

```
router → service → ports (interfaces)
                     ▲
dependencies ────────┴── repository propio y public.py de otros módulos
```

1. Un servicio solo importa archivos de su módulo. Lo que necesita de otro lo declara en `ports.py`.
2. Entre módulos se usa `public.py`, conectado en `dependencies.py`. Los routers solo usan el de `auth`.
3. Dos excepciones: un `schemas.py` puede anidar contratos de otro módulo, y un `repository.py` puede leer modelos de otro para cargar relaciones en una sola consulta.
4. `core` no conoce a ningún módulo.
5. Las reglas de negocio no importan FastAPI, SQLAlchemy, repositorios ni schemas.

`tests/test_architecture.py` comprueba estas reglas: si se rompen, fallan los tests.

Compromiso aceptado: los servicios usan directamente los modelos de SQLAlchemy de su módulo. Tener entidades aparte obligaría a convertir datos en cada operación, demasiado para un proyecto básico.

## Cómo agregar un módulo

1. Crea `app/modules/<nombre>/` con los archivos de la tabla anterior.
2. Regístralo en `app/router.py` y `app/models.py`.
3. Genera la migración: `alembic revision --autogenerate -m "descripcion"`.
4. Agrega sus tests en `tests/<nombre>/` y su permiso en `app/modules/auth/permissions.py` (y en el test de permisos de `tests/auth/test_api.py`).
5. Escribe su `spec.md`.

## Decisiones de diseño

| Decisión | Razón |
|---|---|
| Módulos por negocio | Un cambio en empleados se hace en una carpeta |
| Contratos separados por operación | Cada uno evoluciona sin afectar a los demás |
| Catálogo de puestos en tabla propia | No se escriben puestos como texto libre |
| Baja lógica | El historial se conserva |
| `NUMERIC(12,2)` y `Decimal` | Sin errores de redondeo en salarios |
| Índice único parcial | La base garantiza un solo puesto activo por empleado |
| Commit antes de responder | El cliente nunca recibe un 201 de algo no guardado |
| Lock de jerarquía | Dos peticiones simultáneas no pueden crear un ciclo |
| UUID como identificador | No se pueden adivinar ni enumerar |

## Idempotencia

| Operación | Al repetirla |
|---|---|
| GET | Mismo resultado |
| PATCH con los mismos datos | Sin cambios, ni en `updated_at` |
| DELETE de un empleado | 204 también si ya estaba de baja |
| POST de empleado, puesto del catálogo o departamento | 409: el email o el nombre ya existe |
| POST de asignación de puesto | 409 `overlapping_position` |

Ante un 409 tras un reintento, el cliente recupera el recurso con GET; por ejemplo, `/employees?email=...`.

## Pool de conexiones

Cada worker tiene su propio pool: conexiones máximas = workers × (`DATABASE_POOL_SIZE` + `DATABASE_MAX_OVERFLOW`). Con 4 workers y los valores por defecto son 60; PostgreSQL acepta 100 por defecto.

## Fuera de alcance

Varias monedas, permisos por departamento, registro de auditoría y pooler externo.
