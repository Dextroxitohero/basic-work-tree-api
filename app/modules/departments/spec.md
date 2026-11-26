# Módulo `departments`

Departamentos y sus encargados.

## Endpoints

| Método | Ruta | Entrada | Salida | Permiso |
|---|---|---|---|---|
| GET | `/departments` | `q`, `sort`, `order`, `after` (query) | `Page[DepartmentResponse]` | `employees:read` |
| POST | `/departments` | `DepartmentCreate` | 201 `DepartmentResponse` | `departments:write` |
| GET | `/departments/{id}` | — | `DepartmentResponse` | `employees:read` |
| PATCH | `/departments/{id}` | `DepartmentUpdate` | `DepartmentResponse` | `departments:write` |

## Listado: `GET /departments`

Paginado por cursor (contrato en [`core`](../../core/spec.md#paginación-por-cursor)); el tamaño de página es 50.

| Parámetro | Tipo | Efecto |
|---|---|---|
| `q` | texto, 1 a 100 | Coincidencia parcial, sin distinguir mayúsculas, en `name` |
| `sort` | `name`, `created_at` | Por defecto `name` |
| `order` | `asc`, `desc` | Por defecto `asc` |
| `after` | cursor | El `next_cursor` de la página anterior |

Un `sort`, `order`, `after` o `q` inválido da 422 `validation_error`.

## Respuesta

`DepartmentResponse` (en lista, detalle, creación y edición): `id`, `name`, `manager_id`, `employee_count` y `created_at`. `employee_count` cuenta los empleados **activos** del departamento. El detalle no incluye los empleados: se piden con `GET /employees?department_id=…`.

## Validaciones

| Campo | Regla |
|---|---|
| `name` | 1 a 100 caracteres, sin espacios en los extremos |
| `manager_id` | Opcional; en PATCH, `null` quita al encargado |

En PATCH, `name` no acepta `null`.

## Reglas de negocio

| Regla | Error |
|---|---|
| El departamento debe existir | 404 `department_not_found` |
| El nombre es único | 409 `department_name_exists` |
| El encargado debe existir | 404 `employee_not_found` |
| El encargado debe estar activo | 409 `inactive_manager` |

## Tabla `departments`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `UUID` | PK |
| `name` | `VARCHAR(100)` | NOT NULL, UNIQUE |
| `manager_id` | `UUID` | FK `employees`, índice |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

Índices: `manager_id`, `(created_at, id)` para el orden por creación y el índice único de `name`, que sirve al orden por nombre. `employee_count` no es una columna: se calcula en cada consulta.

`departments` y `employees` se referencian mutuamente: `use_alter=True` crea esta FK cuando ya existen ambas tablas.

## Relación con otros módulos

| Dirección | Qué |
|---|---|
| Ofrece (`public.py`) | `DepartmentDirectory`: `ensure_exists`, `release_manager` |
| Necesita (`ports.py`) | `Managers.ensure_can_manage` (de employees) |
