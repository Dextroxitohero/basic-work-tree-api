# Módulo `departments`

Departamentos y sus encargados.

## Endpoints

| Método | Ruta | Entrada | Salida | Permiso |
|---|---|---|---|---|
| GET | `/departments` | — | `list[DepartmentResponse]` | `employees:read` |
| POST | `/departments` | `DepartmentCreate` | 201 `DepartmentResponse` | `departments:write` |
| GET | `/departments/{id}` | — | `DepartmentDetail` | `employees:read` |
| PATCH | `/departments/{id}` | `DepartmentUpdate` | `DepartmentResponse` | `departments:write` |

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

El detalle muestra solo empleados activos.

## Tabla `departments`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `UUID` | PK |
| `name` | `VARCHAR(100)` | NOT NULL, UNIQUE |
| `manager_id` | `UUID` | FK `employees`, índice |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

`departments` y `employees` se referencian mutuamente: `use_alter=True` crea esta FK cuando ya existen ambas tablas.

## Relación con otros módulos

| Dirección | Qué |
|---|---|
| Ofrece (`public.py`) | `DepartmentDirectory`: `ensure_exists`, `release_manager` |
| Necesita (`ports.py`) | `Managers.ensure_can_manage` (de employees) |
