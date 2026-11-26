# Módulo `employees`

Empleados, jerarquía de jefes y organigrama.

## Endpoints

| Método | Ruta | Entrada | Salida | Permiso |
|---|---|---|---|---|
| GET | `/employees` | Filtros, orden y cursor (query, ver abajo) | `Page[EmployeeResponse]` | `employees:read` |
| POST | `/employees` | `EmployeeCreate` | 201 `EmployeeResponse` | `employees:write` |
| GET | `/employees/{id}` | — | `EmployeeDetail` | `employees:read` |
| PATCH | `/employees/{id}` | `EmployeeUpdate` | `EmployeeResponse` | `employees:write` |
| DELETE | `/employees/{id}` | — | 204 | `employees:write` |
| GET | `/employees/{id}/reports` | — | `list[EmployeeResponse]` | `employees:read` |
| GET | `/employees/{id}/tree` | — | `EmployeeTreeNode` | `employees:read` |

## Listado: `GET /employees`

Paginado por cursor (contrato en [`core`](../../core/spec.md#paginación-por-cursor)). El tamaño de página lo fija el servidor (50).

| Parámetro | Tipo | Efecto |
|---|---|---|
| `is_active` | `bool` | Omitido: activos e inactivos. `true` o `false` filtra |
| `email` | email | Coincidencia exacta, sin distinguir mayúsculas |
| `q` | texto, 1 a 100 | Coincidencia parcial, sin distinguir mayúsculas, en `first_name`, `last_name` y `email` |
| `department_id` | UUID | Empleados de ese departamento |
| `manager_id` | UUID | Subordinados directos de ese jefe |
| `has_manager` | `bool` | `false`: las raíces del organigrama; `true`: quienes tienen jefe |
| `job_title_id` | UUID | Empleados cuyo puesto **actual** es ese |
| `sort` | `last_name`, `first_name`, `hire_date`, `created_at` | Por defecto `last_name` |
| `order` | `asc`, `desc` | Por defecto `asc` |
| `after` | cursor | El `next_cursor` de la página anterior |

Los filtros se combinan con AND. Un valor inválido en `sort`, `order`, `after` o `q` (vacío) da 422 `validation_error`; también un cursor mal formado o creado con otro `sort` u `order`. Un filtro por un id que no existe devuelve una página vacía, no un 404.

## Validaciones

| Campo | Regla |
|---|---|
| `first_name`, `last_name` | 1 a 80 caracteres, sin espacios en los extremos |
| `email` | Formato válido; se guarda en minúsculas; no se puede cambiar |
| `phone` | 1 a 20 caracteres, opcional |
| `hire_date` | No puede ser futura |

En PATCH, `phone`, `manager_id` y `department_id` aceptan `null`; `first_name`, `last_name` e `is_active` no.

## Reglas de negocio

| Regla | Error |
|---|---|
| El empleado debe existir | 404 `employee_not_found` |
| El email es único | 409 `email_already_exists` |
| El jefe debe existir | 404 `employee_not_found` |
| El jefe debe estar activo | 409 `inactive_manager` |
| No puede haber ciclos de jefes | 409 `circular_manager_reference` |
| El departamento debe existir | 404 `department_not_found` |

**Baja** (`DELETE` o `PATCH {"is_active": false}`): cierra el puesto actual con la fecha de hoy, deja sin jefe a sus subordinados y sin encargado a sus departamentos. Conserva el historial y repetirla no cambia nada. Al reactivar no se recuperan.

## Tabla `employees`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `UUID` | PK |
| `first_name`, `last_name` | `VARCHAR(80)` | NOT NULL |
| `email` | `VARCHAR(254)` | NOT NULL, UNIQUE |
| `phone` | `VARCHAR(20)` | |
| `hire_date` | `DATE` | NOT NULL |
| `is_active` | `BOOLEAN` | NOT NULL, `true` |
| `manager_id` | `UUID` | FK `employees`, índice |
| `department_id` | `UUID` | FK `departments`, índice |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | NOT NULL |

Índices para filtrar, ordenar y paginar: `manager_id`, `department_id` y, con el `id` como segunda columna, `(last_name, id)`, `(first_name, id)`, `(hire_date, id)` y `(created_at, id)`.

## Relación con otros módulos

| Dirección | Qué |
|---|---|
| Ofrece (`public.py`) | `EmployeeDirectory`: `ensure_exists`, `ensure_active`, `ensure_can_manage` |
| Necesita (`ports.py`) | `Positions.close_current` (de positions); `Departments.ensure_exists` y `release_manager` (de departments) |

## Concurrencia

`lock_hierarchy` usa un lock de PostgreSQL que se libera al terminar la transacción. Lo toman las asignaciones de jefe o encargado, las asignaciones de puesto y las bajas. Evita que dos peticiones simultáneas creen un ciclo.
