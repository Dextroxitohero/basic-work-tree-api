# Núcleo (`core`)

Piezas técnicas comunes. No conoce a ningún módulo de negocio.

| Archivo | Contenido |
|---|---|
| `config.py` | Configuración por entorno (`APP_ENV`), validada al arrancar (incluye `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` y `CORS_ORIGINS`) |
| `database.py` | Pool, sesión por petición (`get_db`) y `DbSession` |
| `models.py` | Base de SQLAlchemy, mixins y nombres de constraints |
| `schemas.py` | Contratos base: `InputModel`, `PatchModel`, `OutputModel`, `PageResponse`, `ErrorResponse` |
| `repository.py` | `flush`: traduce violaciones de unicidad |
| `pagination.py` | Paginación por cursor: `Page`, cursor, orden y búsqueda parcial |
| `rate_limit.py` | `SlidingWindowLimiter`: límite de intentos en memoria |
| `client_ip.py` | `client_ip`: la IP del cliente detrás de un proxy, sin fiarse del cliente |
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
| `InvalidInputError` (cursor inválido) | 422 `validation_error` |
| `TooManyRequestsError` | 429, con `Retry-After` (segundos) |
| `HTTPException` del framework | su código, `http_error` |
| Cualquier otra | 500 `internal_error`; el detalle solo va al log |

Cada módulo define sus errores heredando de una categoría. Todas las respuestas usan `ErrorResponse`.

## Paginación por cursor

Los listados de empleados y departamentos usan el mismo contrato.

**Petición:** `?after=<cursor>`. No hay `limit` ni `offset` (si se envían, se ignoran): el servidor fija el tamaño de página, `PAGE_SIZE = 50`.

**Respuesta:**

```json
{ "items": [ ... ], "next_cursor": "eyJz..." }
```

`next_cursor` es `null` en la última página. El cliente lo envía tal cual en `after`; es opaco y no debe interpretarlo.

**Cómo funciona:** el cursor guarda la última fila entregada como el par `(valor_de_orden, id)`, y la página siguiente empieza justo después:

```sql
WHERE (columna_de_orden, id) > (:valor, :id)   -- con order=desc, <
ORDER BY columna_de_orden, id                  -- con order=desc, ambos descendentes
LIMIT 51                                       -- una fila de más indica que hay otra página
```

- El `id` desempata filas con el mismo valor de orden, así el orden es total y estable. Con UUID v4 no se puede ordenar por `id` y esperar orden cronológico, pero con el par compuesto no hace falta UUID v7.
- A diferencia de `OFFSET`, no repite ni salta filas si se crean o borran registros entre dos páginas, y la base de datos no recorre las filas anteriores. Cada columna de orden tiene un índice `(columna, id)`.
- El cursor lleva también `sort` y `order`: uno creado con otro orden se rechaza.
- Un cursor mal formado, de otro orden o con un valor inválido para su columna da **422** `validation_error`, igual que un `sort` u `order` no permitido.

**Búsqueda `q`:** coincidencia parcial sin distinguir mayúsculas (`ILIKE '%q%'`). Los caracteres `%` y `_` se buscan como texto, no como comodines. No usa índice: es un recorrido de la tabla, aceptable con este volumen.

**Cómo agregar un listado paginado:** declarar un `SortSpec` por cada columna ordenable (con su índice `(columna, id)`), llamar a `apply_page` sobre el `SELECT` y devolver `build_page(...)`. El router responde con `PageResponse[...]`.

## CORS

`CORSMiddleware` autoriza a los orígenes de `CORS_ORIGINS` (separados por comas, sin barra final; por defecto ninguno). Permite los métodos `GET`, `POST`, `PATCH` y `DELETE` (el preflight `OPTIONS` lo gestiona el middleware) y los headers `Authorization` y `Content-Type`. No admite credenciales: el token viaja en el header, no en cookies.

## Entornos

`APP_ENV` es la bandera: `dev` (por defecto) o `production`. `build_settings` la lee de la variable de entorno, luego de `.env`, y carga los archivos `.env` y `.env.<APP_ENV>`. Prioridad, de menor a mayor: `.env`, `.env.<entorno>`, variables de entorno reales. Un valor distinto de `dev` o `production`, o un archivo cargado que diga otro entorno, impide arrancar.

En `production` el modelo `Settings` rechaza, y lista todos a la vez: `DEBUG=true`, `CORS_ORIGINS` con `*` y un `DATABASE_URL` cuyo host sea `localhost`, `127.0.0.1` o `::1`. En `dev` no hay restricciones. La imagen Docker fija `APP_ENV=production`; `.env.*` no entra en la imagen (`.dockerignore`) y no se sube al repositorio (`.gitignore`), salvo las plantillas `*.example`.

## Configuración

| Variable | Obligatoria | Regla |
|---|---|---|
| `APP_ENV` | No | `dev` o `production`. Por defecto `dev` |
| `DATABASE_URL` | Sí | `postgres://` y `postgresql://` se convierten a `postgresql+asyncpg://` |
| `JWT_SECRET` | Sí | Mínimo 32 caracteres. Sin valor por defecto |
| `ADMIN_EMAIL` | Sí | Se guarda en minúsculas |
| `ADMIN_PASSWORD` | Sí | Mínimo 12 caracteres. Sin valor por defecto |
| `TRUSTED_PROXY_HOPS` | No | Proxies de confianza delante de la app, de 0 a 5. Por defecto 0; el `Dockerfile` lo fija en 1 |
| `CORS_ORIGINS` | No | Orígenes separados por comas |

Sin las tres variables de autenticación la aplicación no arranca. Los secretos son `SecretStr`: no aparecen al imprimir la configuración. Las variables `AUTH0_*`, `AUTH_MODE` y `LOCAL_JWT_SECRET` ya no existen; si siguen en el `.env`, se ignoran.

## Límite de intentos

`SlidingWindowLimiter(limit, window)` permite como máximo `limit` eventos por clave en los últimos `window` segundos. `hit` comprueba y cuenta; `check` solo comprueba; `record` solo cuenta; `reset` borra una clave. Al superar el límite lanza `TooManyRequestsError(retry_after=...)`.

Los contadores viven en memoria de cada proceso: con varios workers el límite efectivo es `limit` por worker. Las claves vencidas se descartan periódicamente para que la memoria no crezca. Lo usa el módulo `auth`.

## IP del cliente detrás de un proxy

`client_ip(request, trusted_hops)` devuelve la IP que sirve de clave para el límite de intentos. Cada proxy de confianza **añade al final** de `X-Forwarded-For` la IP de quien se le conectó:

```
X-Forwarded-For: <lo que escribió el cliente>, <IP real, añadida por el proxy>
```

Todo lo que está a la izquierda lo controla el cliente. Por eso se cuenta desde la derecha: con `trusted_hops=1` es el último elemento; con 2, el penúltimo.

| Situación | Resultado |
|---|---|
| `trusted_hops=0` (por defecto) | Se ignora el header y se usa la IP de la conexión |
| Header ausente, más corto que `trusted_hops`, o con una entrada que no es una IP | La IP de la conexión (nunca un valor del cliente) |
| IPv6 | Se agrupa por bloque `/64`, para que rotar direcciones dentro del bloque no salte el límite |

uvicorn se arranca con `--no-proxy-headers`: con `--forwarded-allow-ips='*'` tomaría el **primer** elemento del header, que escribe el cliente. Si hay otro proxy delante de Railway (un CDN, por ejemplo), sube `TRUSTED_PROXY_HOPS` a 2.

## Errores de la base de datos

El motor se crea con `hide_parameters=True`. Sin esa opción, SQLAlchemy incluye los valores de la consulta en el mensaje de sus errores: un INSERT fallido en `users` dejaría el email y el hash de la contraseña en los logs (y con `DEBUG=true`, también en el `echo` de cada consulta). Alembic usa la misma opción.

## Contratos base

| Clase | Comportamiento |
|---|---|
| `InputModel` | Un campo desconocido da 422 |
| `PatchModel` | Distingue un campo omitido de uno en `null`; rechaza `null` en los de `not_nullable` |
| `OutputModel` | Se construye desde los atributos de un objeto |
| `PageResponse[T]` | `items` y `next_cursor` de los listados paginados |

## Convenciones de modelos

- `eager_defaults`: los valores generados por la base llegan con el propio INSERT o UPDATE.
- `NAMING_CONVENTION`: nombres de constraints predecibles; los repositorios dependen de ellos.
- Las relaciones son de solo lectura (`viewonly`) y con `lazy="raise"`, para evitar consultas ocultas.
