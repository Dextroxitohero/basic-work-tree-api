# Módulo `auth`

Usuarios, sesiones y permisos. Responde dos preguntas: quién eres (autenticación) y qué puedes hacer (autorización). La API guarda sus propios usuarios y emite sus propios tokens JWT; un único verificador los valida.

## Endpoints

| Método | Ruta | Entrada | Salida | Acceso |
|---|---|---|---|---|
| POST | `/auth/signup` | `SignupRequest` | 201 `AuthSession` | Público |
| POST | `/auth/login` | `LoginRequest` | 200 `AuthSession` | Público |
| GET | `/auth/me` | — | `AuthUser` | Token |
| GET | `/users` | `is_active`, `q`, `sort`, `order`, `after` (query) | `Page[AuthUser]` | `users:write` |
| PATCH | `/users/{id}` | `UserUpdate` | `AuthUser` | `users:write` |

## Contratos

| Contrato | Campos |
|---|---|
| `SignupRequest` | `full_name` (1 a 120), `email` (válido, se guarda en minúsculas), `password` (8 a 128). Ningún otro campo: los permisos jamás vienen del body |
| `LoginRequest` | `email`, `password` (1 a 128) |
| `AuthUser` | `id`, `email`, `full_name` (puede ser `null`), `is_active`, `permissions` |
| `AuthSession` | `access_token`, `token_type` (siempre `"bearer"`), `expires_in` (segundos, 43200) y `user` |
| `UserUpdate` | `permissions` (lista de permisos conocidos, sin duplicados) e `is_active`. Ninguno acepta `null`; los campos omitidos no se tocan |

`GET /users` pagina por cursor con el contrato de [`core`](../../core/spec.md#paginación-por-cursor). `q` busca en email y nombre; `sort` es `email` (por defecto) o `created_at`; sin `is_active` devuelve activos e inactivos.

## Archivos

| Archivo | Contenido |
|---|---|
| `router.py` | `/auth/*` y `/users/*` |
| `dependencies.py` | `get_current_user`, `require_permission` y el montaje del servicio |
| `service.py` | `AuthService`: signup, login, autenticar, gestionar usuarios y `ensure_admin` |
| `ports.py` | `UserStore`, `PasswordHasher` y `TokenIssuer` |
| `repository.py` | Acceso a la tabla `users` |
| `passwords.py` | `Argon2PasswordHasher` |
| `tokens.py` | `JwtTokens`: emite y verifica |
| `guard.py` | `AuthGuard`: límite de intentos |
| `permissions.py` | Los permisos y sus constantes |
| `models.py`, `schemas.py`, `exceptions.py` | Modelo, contratos y errores |
| `public.py` | `require_permission`, lo único que usan otros módulos |

## Flujo de una petición

1. `HTTPBearer` extrae el token de `Authorization: Bearer <token>`.
2. `JwtTokens.verify` comprueba firma, caducidad, audiencia y emisor. No consulta la base de datos.
3. `AuthService.authenticate` carga al usuario de la base. Si no existe o está desactivado, responde 401 `invalid_token` aunque el token no haya caducado.
4. `require_permission("...")` comprueba `permissions` **del usuario cargado**, no los del token. Un cambio de permisos o una desactivación surten efecto en la siguiente petición.

## Contraseñas

| Aspecto | Comportamiento |
|---|---|
| Algoritmo | Argon2id (`argon2-cffi`, parámetros por defecto de la librería) |
| Almacenamiento | Solo el hash, en `users.password_hash`. La contraseña no se guarda, no se devuelve y no se escribe en logs |
| Contraseña en los contratos | `SecretStr`: aparece como `**********` si el objeto se imprime |
| Errores de validación | La respuesta 422 no incluye el valor enviado |
| Ejecución | En otro hilo, para no bloquear el event loop |
| Tiempo constante | Si el email no existe, el login verifica contra un hash falso: tarda lo mismo y no delata qué emails están registrados |

## Tokens (JWT)

| Claim | Valor |
|---|---|
| Algoritmo | `HS256`, firmado con `JWT_SECRET`. La API fija el algoritmo; el del token no decide |
| `sub` | Id del usuario (UUID) |
| `email` | Email del usuario |
| `permissions` | Permisos en el momento de emitirlo (informativo: la API usa los de la base) |
| `iss` y `aud` | `employee-work-tree-api` |
| `iat` y `exp` | Emisión y caducidad, 12 horas después |

`sub`, `exp`, `iss` y `aud` son obligatorios. Un token firmado con otro secreto, caducado, con otra audiencia o emisor, con `alg: none` o con `sub` que no sea un UUID da 401 `invalid_token`.

## Reglas de negocio

| Regla | Error |
|---|---|
| Email o contraseña incorrectos (mismo mensaje en ambos casos) | 401 `invalid_credentials` |
| Token ausente, caducado, inválido, o de un usuario inexistente o desactivado | 401 `invalid_token` |
| El email ya está registrado (sin distinguir mayúsculas) | 409 `user_email_exists` |
| La cuenta está desactivada y la contraseña es correcta | 403 `account_disabled` |
| Falta el permiso | 403 `insufficient_permissions` (con `details.required`) |
| El usuario no existe | 404 `user_not_found` |
| La operación dejaría el sistema sin un administrador activo | 409 `last_admin_required` |
| Demasiados intentos | 429 `too_many_requests`, con `Retry-After` |
| Body inválido, permiso desconocido o campo extra | 422 `validation_error` |

Con una cuenta desactivada y una contraseña incorrecta, el login responde 401 `invalid_credentials`: la desactivación solo se revela a quien conoce la contraseña.

## Permisos

| Permiso | Permite |
|---|---|
| `employees:read` | Todos los GET de empleados, puestos y departamentos |
| `employees:write` | Crear, editar y dar de baja empleados |
| `positions:write` | Asignar puestos |
| `job-titles:write` | Crear y editar el catálogo de puestos |
| `departments:write` | Crear y editar departamentos |
| `users:write` | Listar usuarios y cambiar sus permisos o su estado |

`employees:read` incluye los salarios de todos los empleados. Quien se registra con `/auth/signup` recibe solo `employees:read`; el resto lo concede un administrador con `PATCH /users/{id}`.

## Administrador

Un administrador es un usuario **activo** con `users:write`. El sistema siempre conserva al menos uno:

- `PATCH /users/{id}` responde 409 `last_admin_required` si quitaría `users:write` al último administrador activo, o si lo desactivaría.
- Los cambios de usuarios se serializan con un lock de PostgreSQL, así dos administradores que se quitan el permiso a la vez no pueden dejar el sistema sin ninguno.
- Un usuario desactivado con `users:write` no cuenta como administrador.

**Administrador sembrado** (`app/seed/admin.py`): con `ADMIN_EMAIL` y `ADMIN_PASSWORD`, en cada arranque de la API (`lifespan`) y con `python -m app.seed`:

| Situación | Resultado |
|---|---|
| No existe | Se crea, activo y con todos los permisos |
| Existe y está sano | No se toca |
| Existe pero está desactivado o le faltan permisos | Se reactiva y recupera todos los permisos |
| Existe con otra contraseña | La contraseña **no** se modifica |

Es idempotente y nunca duplica: un lock evita que dos arranques simultáneos lo creen dos veces.

## Límite de intentos

Contadores en memoria por proceso (ver [`core`](../../core/spec.md#límite-de-intentos)):

| Endpoint | Clave | Límite | Efecto |
|---|---|---|---|
| `/auth/login` | IP | 30 intentos por minuto | 429 |
| `/auth/login` | email | 5 contraseñas incorrectas en 15 minutos | 429 incluso con la contraseña correcta, hasta que pase la ventana |
| `/auth/signup` | IP | 10 por hora | 429 |
| `/auth/signup` | email | 3 por hora | 429 |

Un login correcto borra el contador de fallos de ese email. Los emails que no existen se limitan igual, así el 429 no revela si una cuenta existe. Detrás del proxy de Railway, uvicorn se arranca con `--proxy-headers` para que la IP sea la del cliente.

## Tabla `users`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | `UUID` | PK |
| `email` | `VARCHAR(254)` | NOT NULL, UNIQUE, CHECK `email = lower(email)` |
| `full_name` | `VARCHAR(120)` | |
| `password_hash` | `TEXT` | NOT NULL |
| `is_active` | `BOOLEAN` | NOT NULL, `true` |
| `permissions` | `TEXT[]` | NOT NULL, `{employees:read}` |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | NOT NULL |

## Relación con otros módulos

| Dirección | Qué |
|---|---|
| Ofrece (`public.py`) | `require_permission` |
| Necesita | Solo el núcleo (`core`) |

El comando de semilla usa `get_auth_service` para crear al administrador.

## Cambiar la forma de autenticar

El servicio depende de los puertos `PasswordHasher` y `TokenIssuer`, no de Argon2 ni de PyJWT. Para cambiar el algoritmo de hash, escribe otra clase con `hash` y `verify` y devuélvela en `get_password_hasher`. Los tests unitarios del servicio pueden usar versiones en memoria de los tres puertos.
