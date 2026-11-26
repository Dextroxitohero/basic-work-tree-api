# Módulo `job_titles`

Catálogo de puestos de la empresa.

## Endpoints

| Método | Ruta | Entrada | Salida | Permiso |
|---|---|---|---|---|
| GET | `/job-titles` | `is_active`, `q`, `sort`, `order` (query) | `list[JobTitleResponse]` | `employees:read` |
| POST | `/job-titles` | `JobTitleCreate` | 201 `JobTitleResponse` | `job-titles:write` |
| GET | `/job-titles/{id}` | — | `JobTitleResponse` | `employees:read` |
| PATCH | `/job-titles/{id}` | `JobTitleUpdate` | `JobTitleResponse` | `job-titles:write` |

## Listado: `GET /job-titles`

El catálogo es pequeño: se devuelve completo, sin paginar.

| Parámetro | Tipo | Efecto |
|---|---|---|
| `is_active` | `bool` | Omitido: activos e inactivos. `true` o `false` filtra |
| `q` | texto, 1 a 100 | Coincidencia parcial, sin distinguir mayúsculas, en `name` |
| `sort` | `name` | Es el único orden disponible |
| `order` | `asc`, `desc` | Por defecto `asc` |

Un valor inválido da 422 `validation_error`.

## Validaciones

| Campo | Regla |
|---|---|
| `name` | 1 a 120 caracteres, sin espacios en los extremos |
| `description` | Hasta 1000 caracteres, opcional |

En PATCH, `description` acepta `null`; `name` e `is_active` no.

## Reglas de negocio

| Regla | Error |
|---|---|
| El puesto debe existir | 404 `job_title_not_found` |
| El nombre es único, también entre los inactivos | 409 `job_title_name_exists` |
| Un puesto inactivo no se puede asignar | 409 `job_title_inactive` |

Desactivar un puesto no afecta a las asignaciones existentes. No se borran puestos.

## Tabla `job_titles`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `UUID` | PK |
| `name` | `VARCHAR(120)` | NOT NULL, UNIQUE |
| `description` | `TEXT` | |
| `is_active` | `BOOLEAN` | NOT NULL, `true` |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | NOT NULL |

## Relación con otros módulos

| Dirección | Qué |
|---|---|
| Ofrece (`public.py`) | `JobTitleCatalog.ensure_assignable` |
| Necesita | Solo los permisos de auth |
