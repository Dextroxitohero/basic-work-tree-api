# Núcleo (`core`)

Piezas técnicas comunes. No conoce a ningún módulo de negocio.

| Archivo | Contenido |
|---|---|
| `config.py` | Configuración desde `.env`, validada al arrancar |
| `database.py` | Pool, sesión por petición (`get_db`) y `DbSession` |
| `models.py` | Base de SQLAlchemy, mixins y nombres de constraints |
| `schemas.py` | Contratos base: `InputModel`, `PatchModel`, `OutputModel`, `ErrorResponse` |
| `repository.py` | `flush`: traduce violaciones de unicidad |
| `exceptions.py` | Categorías de error |
| `error_handlers.py` | Categoría de error → respuesta HTTP |
| `responses.py` | Documenta los errores en OpenAPI |

## Transacciones

Una petición usa una sesión y una transacción. `get_db` hace commit si todo va bien y rollback si algo falla. Con `scope="function"`, el commit ocurre antes de enviar la respuesta. Los repositorios hacen `flush`, nunca `commit`.

## Errores

| Categoría | HTTP |
|---|---|
| `UnauthenticatedError` | 401, con `WWW-Authenticate: Bearer` |
| `ForbiddenError` | 403 |
| `NotFoundError` | 404 |
| `ConflictError` | 409 |
| `RequestValidationError` (Pydantic) | 422 `validation_error` |
| `ServiceUnavailableError` | 503 |
| `HTTPException` del framework | su código, `http_error` |
| Cualquier otra | 500 `internal_error`; el detalle solo va al log |

Cada módulo define sus errores heredando de una categoría. Todas las respuestas usan `ErrorResponse`.

## Contratos base

| Clase | Comportamiento |
|---|---|
| `InputModel` | Un campo desconocido da 422 |
| `PatchModel` | Distingue un campo omitido de uno en `null`; rechaza `null` en los de `not_nullable` |
| `OutputModel` | Se construye desde los atributos de un objeto |

## Convenciones de modelos

- `eager_defaults`: los valores generados por la base llegan con el propio INSERT o UPDATE.
- `NAMING_CONVENTION`: nombres de constraints predecibles; los repositorios dependen de ellos.
- Las relaciones son de solo lectura (`viewonly`) y con `lazy="raise"`, para evitar consultas ocultas.
