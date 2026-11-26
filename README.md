# Employee Work Tree API

API REST para registrar a los empleados de una empresa: sus datos, el historial de puestos con salario y fechas, los departamentos y la jerarquía de jefes.

Es un proyecto de práctica con **FastAPI**, **Pydantic v2**, **SQLAlchemy async** y **PostgreSQL**, con el código comentado para aprender el framework.

## Contenido

- [Inicio rápido](#inicio-rápido)
- [Datos de ejemplo](#datos-de-ejemplo)
- [Uso](#uso)
- [Endpoints](#endpoints)
- [Configuración](#configuración)
- [Autenticación](#autenticación)
- [Desarrollo](#desarrollo)
- [Estructura](#estructura)
- [Problemas frecuentes](#problemas-frecuentes)

## Inicio rápido

Necesitas Python 3.12 o superior (probado con 3.13) y Docker con Docker Compose. Los comandos son para PowerShell, desde la raíz del proyecto.

**1. Instala las dependencias y crea la configuración**

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item .env.example .env
Copy-Item .env.dev.example .env.dev
```

`.env` guarda la bandera `APP_ENV` y `.env.dev` la configuración de desarrollo. Ver [Entornos](#entornos-dev-y-production).

**2. Configura el administrador y el secreto de los tokens**

Genera un secreto:

```powershell
.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Rellena estas tres líneas del archivo `.env.dev`. La app no arranca si falta alguna:

```env
JWT_SECRET=el-secreto-generado
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=una-contraseña-de-12-o-mas-caracteres
```

**3. Arranca la base de datos, crea las tablas y carga los datos de ejemplo**

```powershell
docker compose up -d --wait
.venv\Scripts\alembic upgrade head
.venv\Scripts\python -m app.seed
```

**4. Arranca el servidor**

```powershell
.venv\Scripts\uvicorn app.main:app --reload --port 8010
```

**5. Entra como admin**

Al arrancar, la API crea al administrador con `ADMIN_EMAIL` y `ADMIN_PASSWORD`. Abre http://localhost:8010/docs, ejecuta `POST /auth/login` con ese email y contraseña, copia el `access_token` de la respuesta, pulsa **Authorize** y pégalo (sin el prefijo `Bearer`). También hay documentación en http://localhost:8010/redoc.

Para obtener un token a mano:

```powershell
$login = Invoke-RestMethod -Method Post -Uri "http://localhost:8010/api/v1/auth/login" -ContentType "application/json" -Body (@{ email = "admin@example.com"; password = "TU_ADMIN_PASSWORD" } | ConvertTo-Json)
$login.access_token
```

> En macOS o Linux usa `python3 -m venv .venv`, `.venv/bin/` en lugar de `.venv\Scripts\` y `cp` en lugar de `Copy-Item`.

## Datos de ejemplo

`python -m app.seed` crea 20 empleados con puestos actuales distintos, 5 departamentos con encargado y un historial de puestos. Se puede repetir: no duplica ni modifica lo que ya existe. Solo funciona contra una base de datos local.

```
Elena Vargas — Dirección General
├── Marcos Ibáñez — Dirección de Tecnología
│   ├── Diego Campos — Líder de Desarrollo
│   │   ├── Javier Ortega — Desarrollo Backend Senior
│   │   │   └── Mateo Reyes — Desarrollo Backend Junior
│   │   ├── Carmen Lozano — Desarrollo Frontend Senior
│   │   ├── Valeria Cruz — Diseño UX/UI
│   │   └── Raúl Peña — Control de Calidad
│   └── Sofía Navarro — Líder de Infraestructura
│       ├── Irene Soto — Ingeniería DevOps
│       └── Hugo Medina — Soporte Técnico
├── Lucía Ferrer — Dirección de Recursos Humanos
│   ├── Natalia Gil — Selección de Personal
│   └── Óscar Delgado — Nóminas
├── Andrés Molina — Dirección Financiera
│   ├── Beatriz Santos — Contabilidad
│   └── Tomás Aguilar — Análisis Financiero
└── Paula Rivas — Dirección Comercial
    └── Clara Vidal — Gerencia de Ventas
        └── Iván Romero — Asesoría Comercial
```

El email de cada uno es `nombre.apellido@example.com`, sin tildes ni eñes. El administrador es un usuario de acceso a la API, no un empleado.

## Uso

Con el servidor encendido y la semilla cargada, desde PowerShell:

```powershell
$api = "http://localhost:8010/api/v1"
$login = Invoke-RestMethod -Method Post -Uri "$api/auth/login" -ContentType "application/json" -Body (@{ email = "admin@example.com"; password = "TU_ADMIN_PASSWORD" } | ConvertTo-Json)
$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }

function Get-Api($path) {
    Invoke-RestMethod -Uri "$api$path" -Headers $headers
}

function Send-Api($method, $path, $body) {
    # Se envía en UTF-8 para que las tildes lleguen bien también desde PowerShell 5.1.
    $bytes = [Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json))
    Invoke-RestMethod -Method $method -Uri "$api$path" -Headers $headers -ContentType "application/json" -Body $bytes
}
```

Consultar:

```powershell
# Buscar a un empleado por email
$diego = (Get-Api "/employees?email=diego.campos@example.com").items[0]

# Su equipo completo y su historial de puestos
Get-Api "/employees/$($diego.id)/tree" | ConvertTo-Json -Depth 10
Get-Api "/employees/$($diego.id)/positions"
```

Crear un empleado y asignarle un puesto:

```powershell
$nuevo = Send-Api Post "/employees" @{
    first_name = "Laura"
    last_name  = "Pons"
    email      = "laura.pons@example.com"
    hire_date  = "2025-01-13"
    manager_id = $diego.id
}

$puesto = Get-Api "/job-titles" | ForEach-Object { $_ } | Where-Object name -eq "Desarrollo Backend Junior"

# Si ya tenía un puesto, la API cierra el anterior
Send-Api Post "/employees/$($nuevo.id)/positions" @{
    job_title_id = $puesto.id
    salary       = "1900.00"
    start_date   = "2025-01-13"
}
```

Editar, quitar un valor y dar de baja:

```powershell
Send-Api Patch "/employees/$($nuevo.id)" @{ phone = "555-0100" }
Send-Api Patch "/employees/$($nuevo.id)" @{ manager_id = $null }   # null quita el jefe
Invoke-RestMethod -Method Delete -Uri "$api/employees/$($nuevo.id)" -Headers $headers
```

La baja es lógica: el empleado queda inactivo y conserva su historial. Por eso, si repites el ejemplo, crear a Laura devuelve `409 email_already_exists`; usa otro email.

## Endpoints

Todos van bajo `/api/v1`.

| Método | Ruta | Permiso | Descripción |
|---|---|---|---|
| GET | `/employees` | `employees:read` | Listar con cursor; búsqueda `q`, filtros, `sort` y `order` |
| POST | `/employees` | `employees:write` | Crear |
| GET | `/employees/{id}` | `employees:read` | Detalle con historial y reportes directos |
| PATCH | `/employees/{id}` | `employees:write` | Editar |
| DELETE | `/employees/{id}` | `employees:write` | Dar de baja |
| GET | `/employees/{id}/reports` | `employees:read` | Reportes directos |
| GET | `/employees/{id}/tree` | `employees:read` | Organigrama completo hacia abajo |
| GET | `/employees/{id}/positions` | `employees:read` | Historial de puestos |
| GET | `/employees/{id}/positions/current` | `employees:read` | Puesto actual |
| POST | `/employees/{id}/positions` | `positions:write` | Asignar puesto |
| GET | `/job-titles` | `employees:read` | Listar catálogo; `q`, `is_active`, `order` |
| POST | `/job-titles` | `job-titles:write` | Crear puesto en el catálogo |
| GET | `/job-titles/{id}` | `employees:read` | Detalle |
| PATCH | `/job-titles/{id}` | `job-titles:write` | Editar o descontinuar |
| GET | `/departments` | `employees:read` | Listar con cursor; `q`, `sort` y `order` |
| POST | `/departments` | `departments:write` | Crear |
| GET | `/departments/{id}` | `employees:read` | Detalle, con `employee_count` |
| PATCH | `/departments/{id}` | `departments:write` | Editar o cambiar encargado |

**Listados.** `GET /employees` y `GET /departments` responden `{ "items": [...], "next_cursor": "..." | null }`. Para pedir la página siguiente, envía el `next_cursor` en `?after=`; el tamaño de página (50) lo fija el servidor. `GET /employees` acepta `q`, `email`, `department_id`, `manager_id`, `has_manager`, `job_title_id`, `is_active`, `sort` y `order`; si omites `is_active`, devuelve activos e inactivos. Los detalles están en el spec de cada módulo y en el de [`core`](app/core/spec.md#paginación-por-cursor).

El permiso `employees:read` incluye los salarios de todos los empleados.

Todos los errores tienen la misma forma:

```json
{"error": "employee_not_found", "message": "El empleado no existe", "details": null}
```

## Entornos (dev y production)

Una sola bandera, `APP_ENV`, decide con qué configuración funciona la API. Hay dos valores: `dev` (el de por defecto) y `production`.

| `APP_ENV` | Archivo que se carga | Plantilla | Para qué |
|---|---|---|---|
| `dev` | `.env` y luego `.env.dev` | `.env.dev.example` | Desarrollo local: base de datos de docker compose, front en `localhost` |
| `production` | `.env` y luego `.env.production` | `.env.production.example` | Producción: base de datos de Railway, front desplegado |

Para cambiar de entorno solo se cambia la bandera; cada archivo ya trae sus propios enlaces (`DATABASE_URL`, `CORS_ORIGINS`...):

```env
# .env
APP_ENV=dev           # o production
```

Orden de prioridad, de menor a mayor: `.env`, `.env.<entorno>` y las **variables de entorno reales**. Por eso en Railway no hace falta ningún archivo: se definen las variables en el panel (con `APP_ENV=production`, que la imagen Docker ya fija). Ninguno de estos archivos se sube al repositorio, solo las plantillas `*.example`.

**En `production` la app se niega a arrancar** si `DEBUG=true`, si `CORS_ORIGINS` contiene `*` o si `DATABASE_URL` apunta a una base de datos local. Si `APP_ENV` es otra cosa que `dev` o `production`, o si un archivo se contradice con la bandera (por ejemplo `.env.dev` con `APP_ENV=production`), tampoco arranca.

Los tests siempre se ejecutan en `dev`, sea cual sea la bandera de tu máquina.

> Si ya tenías un único `.env` con toda la configuración, sigue funcionando (el entorno por defecto es `dev`). Para adoptar el nuevo esquema, muévelo a `.env.dev` y deja en `.env` solo `APP_ENV=dev`.

## Configuración

Variables de configuración (en `.env`, `.env.dev`, `.env.production` o en el entorno). Los archivos con secretos no deben subirse al repositorio: ya están en `.gitignore`.

| Variable | Obligatoria | Por defecto | Descripción |
|---|---|---|---|
| `APP_ENV` | No | `dev` | La bandera: `dev` o `production`. Ver [Entornos](#entornos-dev-y-production) |
| `DATABASE_URL` | Sí | — | Conexión a PostgreSQL (`postgresql+asyncpg://...`) |
| `DATABASE_URL_TEST` | Solo tests | — | Base de datos de tests; su nombre debe terminar en `_test` |
| `JWT_SECRET` | Sí | — | Secreto que firma los tokens, mínimo 32 caracteres |
| `ADMIN_EMAIL` | Sí | — | Email del administrador inicial |
| `ADMIN_PASSWORD` | Sí | — | Contraseña del administrador inicial, mínimo 12 caracteres |
| `DATABASE_POOL_SIZE` | No | 10 | Conexiones permanentes por worker |
| `DATABASE_MAX_OVERFLOW` | No | 5 | Conexiones extra por worker en picos |
| `DATABASE_POOL_TIMEOUT` | No | 30 | Segundos de espera por una conexión |
| `DATABASE_POOL_RECYCLE` | No | 1800 | Segundos antes de renovar una conexión |
| `DEBUG` | No | `false` | Muestra el SQL en consola |
| `TRUSTED_PROXY_HOPS` | No | `0` (la imagen Docker usa `1`) | Proxies de confianza delante de la API; define de dónde sale la IP del cliente para el límite de intentos |
| `CORS_ORIGINS` | No | ninguno | Orígenes del front permitidos, separados por comas (`http://localhost:5173,https://mi-front.com`) |

Reinicia el servidor después de cambiar cualquier archivo de configuración.

## Autenticación

La API tiene sus propios usuarios y emite sus propios tokens JWT (HS256, 12 horas). No depende de ningún proveedor externo.

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/auth/signup` | Crea una cuenta con `{full_name, email, password}`. Queda con solo `employees:read` |
| POST | `/auth/login` | `{email, password}` → `{access_token, token_type, expires_in, user}` |
| GET | `/auth/me` | El usuario del token, con sus permisos actuales |
| GET | `/users` | Lista usuarios (`users:write`) |
| PATCH | `/users/{id}` | Cambia `permissions` o `is_active` (`users:write`) |

- Las contraseñas se guardan con Argon2id; nunca se devuelven ni se registran en logs.
- El token se envía en `Authorization: Bearer <token>`. En cada petición la API carga al usuario de la base: si lo desactivas o le cambias los permisos, el efecto es inmediato aunque el token no haya caducado.
- Quien se registra solo recibe lectura. Para darle más permisos, el administrador usa `PATCH /users/{id}`.
- El sistema siempre conserva al menos un administrador activo (un usuario con `users:write`). Quitar ese permiso o desactivar al último da 409 `last_admin_required`.
- Login y signup tienen límite de intentos: tras 5 contraseñas incorrectas para un email, ese email queda bloqueado 15 minutos (429, con `Retry-After`).
- El administrador de `ADMIN_EMAIL` se crea al arrancar si no existe, y si existe se reactiva y recupera todos los permisos. Su contraseña no se modifica. Nadie puede registrarse con ese email, y una cuenta normal que ya lo tenga no se promociona: el arranque lo avisa en el log.

Si olvidas la contraseña del administrador, borra su fila de la tabla `users` y reinicia la API: se crea de nuevo con `ADMIN_PASSWORD`.

Todos los detalles están en el [spec del módulo](app/modules/auth/spec.md).

## Desarrollo

```powershell
.venv\Scripts\python -m pytest        # tests (requiere PostgreSQL encendido)
.venv\Scripts\ruff check .            # linter
.venv\Scripts\ruff format .           # formato
```

Los tests **vacían las tablas** de `DATABASE_URL_TEST`. No usan la base de desarrollo.

Al cambiar un modelo, crea una migración y revísala antes de aplicarla:

```powershell
.venv\Scripts\alembic revision --autogenerate -m "descripcion"
.venv\Scripts\alembic upgrade head
.venv\Scripts\alembic check           # confirma que modelos y base coinciden
```

Para detener PostgreSQL conservando los datos, usa `docker compose down`. Con `-v` también **se borran los datos**.

## Estructura

El código se organiza por módulo de negocio: todo lo de empleados está en `app/modules/employees`, y así con cada uno.

| Ruta | Responsabilidad | Especificación |
|---|---|---|
| `app/modules/employees` | Empleados, jerarquía y organigrama | [spec](app/modules/employees/spec.md) |
| `app/modules/positions` | Historial de puestos, salarios y fechas | [spec](app/modules/positions/spec.md) |
| `app/modules/job_titles` | Catálogo de puestos | [spec](app/modules/job_titles/spec.md) |
| `app/modules/departments` | Departamentos y encargados | [spec](app/modules/departments/spec.md) |
| `app/modules/auth` | Usuarios, login, tokens y permisos | [spec](app/modules/auth/spec.md) |
| `app/core` | Piezas comunes: configuración, base de datos, errores | [spec](app/core/spec.md) |
| `app/seed` | Datos de ejemplo | — |
| `app/main.py` | Crea la aplicación | — |
| `app/router.py` | Reúne los endpoints de los módulos | — |
| `app/models.py` | Registro de tablas para las migraciones | — |
| `alembic` | Migraciones | — |
| `docker` | Crea la base de datos de tests | — |
| `tests` | Tests, una carpeta por módulo | — |

Dentro de un módulo, una petición recorre `router` → `service` → `repository` → PostgreSQL. Los módulos solo se usan entre sí por su `public.py`, y `tests/test_architecture.py` lo comprueba. Las reglas completas y cómo agregar un módulo están en [spec.md](spec.md).

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| No conecta al puerto 5440 | `docker compose up -d --wait` |
| `Field required` al arrancar | Falta una variable en el archivo del entorno (`.env.dev` o `.env.production`) o en el panel de Railway |
| `Configuración no válida para production` | `DEBUG=true`, `CORS_ORIGINS` con `*` o `DATABASE_URL` local: corrígelo, o usa `APP_ENV=dev` |
| `APP_ENV debe ser uno de ('dev', 'production')` | La bandera tiene otro valor |
| La app no arranca y menciona `jwt_secret`, `admin_email` o `admin_password` | Falta esa variable en `.env`, o `JWT_SECRET` tiene menos de 32 caracteres o `ADMIN_PASSWORD` menos de 12 |
| `relation "employees" does not exist` | `alembic upgrade head` |
| 401 `invalid_token` | Token ausente, vencido, de un usuario desactivado o firmado con otro `JWT_SECRET` |
| 401 `invalid_credentials` | Email o contraseña incorrectos |
| 429 `too_many_requests` | Demasiados intentos; espera los segundos de `Retry-After` |
| Log: `ADMIN_EMAIL (...) pertenece a una cuenta normal` | Esa cuenta no se promociona. Usa otro `ADMIN_EMAIL` o borra esa cuenta y reinicia |
| 403 `insufficient_permissions` | Falta el permiso indicado en `details.required` |
| Tildes mal mostradas en PowerShell 5.1 | Solo afecta a la consola; usa Swagger UI o PowerShell 7 |
