# Módulo `positions`

Historial de puestos de cada empleado, con salario y fechas.

## Endpoints

| Método | Ruta | Entrada | Salida | Permiso |
|---|---|---|---|---|
| GET | `/employees/{id}/positions` | — | `list[PositionHistoryResponse]` | `employees:read` |
| GET | `/employees/{id}/positions/current` | — | `PositionHistoryResponse` | `employees:read` |
| POST | `/employees/{id}/positions` | `PositionCreate` | 201 `PositionHistoryResponse` | `positions:write` |

## Validaciones

| Campo | Regla |
|---|---|
| `job_title_id` | UUID del catálogo |
| `salary` | `Decimal` mayor que 0, hasta 12 dígitos con 2 decimales; se devuelve como texto |
| `start_date` | No puede ser futura |
| `notes` | Hasta 500 caracteres, opcional |

## Reglas de negocio

Al asignar un puesto:

1. El empleado debe existir y estar activo: 404 `employee_not_found`, 409 `employee_inactive`.
2. El puesto debe existir en el catálogo y estar activo: 404 `job_title_not_found`, 409 `job_title_inactive`.
3. Si el último puesto está abierto, el nuevo empieza después de su inicio; si está cerrado, después de su fin: 409 `overlapping_position`.
4. El puesto abierto se cierra el día anterior al inicio del nuevo.

Consultar el puesto actual de quien no tiene da 404 `no_active_position`.

## Tabla `position_history`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `UUID` | PK |
| `employee_id` | `UUID` | NOT NULL, FK `employees` |
| `job_title_id` | `UUID` | NOT NULL, FK `job_titles`, índice |
| `salary` | `NUMERIC(12,2)` | NOT NULL, mayor que 0 |
| `start_date` | `DATE` | NOT NULL |
| `end_date` | `DATE` | NULL = puesto actual; no anterior a `start_date` |
| `notes` | `TEXT` | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL |

- `UNIQUE (employee_id, start_date)`: evita duplicados al reintentar.
- `UNIQUE (employee_id) WHERE end_date IS NULL`: un solo puesto activo por empleado.

## Relación con otros módulos

| Dirección | Qué |
|---|---|
| Ofrece (`public.py`) | `PositionCloser.close_current` |
| Necesita (`ports.py`) | `Employees.ensure_exists` y `ensure_active` (de employees); `JobTitles.ensure_assignable` (de job_titles) |
