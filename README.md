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
```

**2. Activa el usuario admin de desarrollo**

Genera un secreto:

```powershell
.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Cambia estas dos líneas del archivo `.env`. La segunda está comentada: quítale el `#` inicial.

```env
AUTH_MODE=local
LOCAL_JWT_SECRET=el-secreto-generado
```

¿Prefieres usar Auth0? Mira [Autenticación](#autenticación).

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

En otra terminal, obtén el token:

```powershell
.venv\Scripts\python -m app.modules.auth.admin_token
```

Abre http://localhost:8010/docs, pulsa **Authorize** y pega el token, sin el prefijo `Bearer`. También hay documentación en http://localhost:8010/redoc.

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

El email de cada uno es `nombre.apellido@example.com`, sin tildes ni eñes. El admin es un usuario aparte, no un empleado.

## Uso

Con el servidor encendido y la semilla cargada, desde PowerShell:

```powershell
$api = "http://localhost:8010/api/v1"
$token = .venv\Scripts\python -m app.modules.auth.admin_token
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
$diego = (Get-Api "/employees?email=diego.campos@example.com")[0]

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
| GET | `/employees` | `employees:read` | Listar; filtros `is_active` y `email` |
| POST | `/employees` | `employees:write` | Crear |
| GET | `/employees/{id}` | `employees:read` | Detalle con historial y reportes directos |
| PATCH | `/employees/{id}` | `employees:write` | Editar |
| DELETE | `/employees/{id}` | `employees:write` | Dar de baja |
| GET | `/employees/{id}/reports` | `employees:read` | Reportes directos |
| GET | `/employees/{id}/tree` | `employees:read` | Organigrama completo hacia abajo |
| GET | `/employees/{id}/positions` | `employees:read` | Historial de puestos |
| GET | `/employees/{id}/positions/current` | `employees:read` | Puesto actual |
| POST | `/employees/{id}/positions` | `positions:write` | Asignar puesto |
| GET | `/job-titles` | `employees:read` | Listar catálogo; filtro `is_active` |
| POST | `/job-titles` | `job-titles:write` | Crear puesto en el catálogo |
| GET | `/job-titles/{id}` | `employees:read` | Detalle |
| PATCH | `/job-titles/{id}` | `job-titles:write` | Editar o descontinuar |
| GET | `/departments` | `employees:read` | Listar |
| POST | `/departments` | `departments:write` | Crear |
| GET | `/departments/{id}` | `employees:read` | Detalle con empleados activos |
| PATCH | `/departments/{id}` | `departments:write` | Editar o cambiar encargado |

Las listas muestran solo registros activos salvo que envíes `is_active=false`. El permiso `employees:read` incluye los salarios de todos los empleados.

Todos los errores tienen la misma forma:

```json
{"error": "employee_not_found", "message": "El empleado no existe", "details": null}
```

## Configuración

Variables del archivo `.env`, que no debe subirse al repositorio (ya está en `.gitignore`):

| Variable | Obligatoria | Por defecto | Descripción |
|---|---|---|---|
| `DATABASE_URL` | Sí | — | Conexión a PostgreSQL (`postgresql+asyncpg://...`) |
| `DATABASE_URL_TEST` | Solo tests | — | Base de datos de tests; su nombre debe terminar en `_test` |
| `AUTH_MODE` | No | `auth0` | `auth0`, o `local` solo para desarrollo |
| `LOCAL_JWT_SECRET` | Con `AUTH_MODE=local` | — | Secreto de al menos 32 caracteres |
| `AUTH0_DOMAIN` | Sí | — | Dominio del tenant, sin `https://` |
| `AUTH0_AUDIENCE` | Sí | — | Identifier de la API; también se usa en modo local |
| `DATABASE_POOL_SIZE` | No | 10 | Conexiones permanentes por worker |
| `DATABASE_MAX_OVERFLOW` | No | 5 | Conexiones extra por worker en picos |
| `DATABASE_POOL_TIMEOUT` | No | 30 | Segundos de espera por una conexión |
| `DATABASE_POOL_RECYCLE` | No | 1800 | Segundos antes de renovar una conexión |
| `DEBUG` | No | `false` | Muestra el SQL en consola |

Reinicia el servidor después de cambiar el `.env`.

## Autenticación

La API no guarda usuarios ni contraseñas: valida un token JWT. Hay dos modos.

### Modo local (desarrollo)

El comando `python -m app.modules.auth.admin_token` emite un token para `admin@example.com`, con todos los permisos y válido 12 horas. Se configura en el paso 2 de [Inicio rápido](#inicio-rápido).

> **No lo uses en producción.** Quien tenga el secreto puede crear tokens de admin.

### Modo Auth0

1. En **Applications > APIs**, crea una API. Su *Identifier* es `AUTH0_AUDIENCE`.
2. En **Settings** de la API, activa **Enable RBAC** y **Add Permissions in the Access Token**.
3. En **Permissions**, crea: `employees:read`, `employees:write`, `positions:write`, `job-titles:write` y `departments:write`.
4. Asigna los permisos a los usuarios (por roles) o a una aplicación *Machine to Machine*.
5. En `.env`, pon `AUTH_MODE=auth0`, `AUTH0_DOMAIN` y `AUTH0_AUDIENCE`.

Para obtener un token de prueba con una aplicación *Machine to Machine*:

```powershell
$auth = Invoke-RestMethod -Method Post -Uri "https://TU_DOMINIO/oauth/token" -Body @{
    grant_type    = "client_credentials"
    client_id     = "TU_CLIENT_ID"
    client_secret = "TU_CLIENT_SECRET"
    audience      = "https://employee-api"
}
$token = $auth.access_token
```

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
| `app/modules/auth` | Autenticación (Auth0 o local) y permisos | [spec](app/modules/auth/spec.md) |
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
| `Field required` al arrancar | Falta una variable en `.env` |
| `AUTH_MODE=local requiere LOCAL_JWT_SECRET` | Genera el secreto y ponlo en `.env` |
| `Solo disponible con AUTH_MODE=local` | Estás en modo Auth0: pide el token a Auth0 o cambia de modo |
| `relation "employees" does not exist` | `alembic upgrade head` |
| 401 `invalid_token` | Token ausente, vencido o de otro modo; reinicia el servidor si cambiaste `.env` |
| 403 `insufficient_permissions` | Falta el permiso indicado en `details.required` |
| 503 `auth_provider_unavailable` | No se alcanza Auth0: revisa `AUTH0_DOMAIN` y la conexión |
| Tildes mal mostradas en PowerShell 5.1 | Solo afecta a la consola; usa Swagger UI o PowerShell 7 |
