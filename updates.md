# Cambios en la API que afectan al front

Resumen para `basic-work-tree-client` de lo que cambió en `basic-work-tree-api`. Los contratos exactos están siempre en `/openapi.json` y en los `spec.md` de cada módulo.

## Contenido

- [Qué rompe el front actual](#qué-rompe-el-front-actual)
- [Autenticación](#autenticación)
- [Administración de usuarios](#administración-de-usuarios)
- [Listados: paginación, búsqueda, filtros y orden](#listados-paginación-búsqueda-filtros-y-orden)
- [Departamentos](#departamentos)
- [Errores](#errores)
- [CORS y entornos](#cors-y-entornos)
- [Tipos de TypeScript](#tipos-de-typescript)
- [Ejemplos](#ejemplos)
- [Pendiente en la API](#pendiente-en-la-api)
- [Lista de tareas para el front](#lista-de-tareas-para-el-front)

## Qué rompe el front actual

| Cambio | Qué hacer |
|---|---|
| Auth0 desapareció | Usar `/auth/signup`, `/auth/login` y `/auth/me`. Quitar el SDK y las variables de Auth0 |
| `GET /employees` y `GET /departments` ya no devuelven un array, sino `{items, next_cursor}` | Usar `useInfiniteQuery` (ver [ejemplos](#ejemplos)) |
| Omitir `is_active` ya **no** significa «solo activos»: devuelve activos e inactivos, en `/employees` y en `/job-titles` | Enviar `is_active=true` explícitamente donde se dependía del valor por defecto, sobre todo en los selects de puestos |
| `GET /departments/{id}` ya no trae `employees` (`DepartmentDetail` no existe) | Pedirlos con `GET /employees?department_id=…`, que está paginado |
| `DepartmentResponse` tiene un campo nuevo, `employee_count` | Actualizar los tipos |
| Los permisos pueden cambiar mientras el token sigue vigente | Tomarlos de `GET /auth/me`, no del token |

## Autenticación

La API tiene sus propios usuarios y emite sus propios JWT (HS256). No depende de ningún proveedor externo.

| Método | Ruta | Cuerpo | Respuesta |
|---|---|---|---|
| POST | `/api/v1/auth/signup` | `{full_name, email, password}` | 201 `AuthSession` |
| POST | `/api/v1/auth/login` | `{email, password}` | 200 `AuthSession` |
| GET | `/api/v1/auth/me` | — | `AuthUser` (requiere token) |

`AuthSession` es `{access_token, token_type: "bearer", expires_in, user}`. `expires_in` está en segundos (43200, es decir, 12 horas). El registro **inicia sesión**: la respuesta ya trae el token, así que no hace falta un login después.

**Reglas de los campos**

| Campo | Regla |
|---|---|
| `full_name` | Obligatorio, 1 a 120 caracteres. Se recortan los espacios de los extremos |
| `email` | Email válido. La API lo guarda en minúsculas |
| `password` (signup) | 8 a 128 caracteres |
| `password` (login) | 1 a 128 caracteres |
| Cualquier otro campo | 422 (por ejemplo `permissions`: no se pueden enviar) |

**Token**

- Se envía en cada petición: `Authorization: Bearer <access_token>`.
- Dura 12 horas. No hay refresh token ni endpoint de logout: cerrar sesión es descartar el token en el cliente, y al caducar hay que volver a iniciar sesión.
- La API consulta al usuario en la base de datos **en cada petición**. Si un administrador lo desactiva o le cambia los permisos, el efecto es inmediato aunque el token no haya caducado.
- Los permisos del token no son la fuente de verdad. Vuelve a pedir `GET /auth/me` al cargar la app y tras cualquier cambio de permisos.

**Permisos**

Quien se registra recibe solo `employees:read`. Los demás los concede un administrador.

| Permiso | Habilita en la interfaz |
|---|---|
| `employees:read` | Ver empleados, puestos, departamentos y organigrama (incluye los salarios) |
| `employees:write` | Crear, editar y dar de baja empleados |
| `positions:write` | Asignar puestos |
| `job-titles:write` | Crear y editar el catálogo de puestos |
| `departments:write` | Crear y editar departamentos |
| `users:write` | Pantalla de administración de usuarios |

Oculta o desactiva en la interfaz lo que el usuario no puede hacer. Eso es solo comodidad: la API siempre lo valida y responde 403 `insufficient_permissions` con `details.required`.

## Administración de usuarios

Requiere `users:write`.

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/users` | Lista paginada. Parámetros: `q` (email o nombre), `is_active`, `sort` (`email` o `created_at`, por defecto `email`), `order`, `after` |
| PATCH | `/api/v1/users/{id}` | Cambia `permissions` (lista de permisos) y/o `is_active`. Los campos omitidos no se tocan; ninguno acepta `null` |

Respuestas de `PATCH`: `AuthUser`. Errores posibles:

| Código | Cuándo |
|---|---|
| 404 `user_not_found` | El id no existe |
| 409 `last_admin_required` | La operación dejaría el sistema sin un administrador activo (quitar `users:write` al último, o desactivarlo) |
| 422 `validation_error` | Permiso desconocido, `null`, o un campo extra |

Los permisos válidos son los seis de la tabla anterior. La API ignora los duplicados y los devuelve ordenados.

## Listados: paginación, búsqueda, filtros y orden

### Paginación por cursor

`GET /employees` y `GET /departments` (y `GET /users`) responden:

```json
{ "items": [ ... ], "next_cursor": "eyJz..." }
```

- `next_cursor` es `null` en la última página.
- Para pedir la siguiente página, envía el valor **tal cual** en `?after=`. Es opaco: no lo decodifiques ni lo construyas.
- El tamaño de página es fijo (50) y lo decide el servidor. `limit` y `offset` no existen y se ignoran.
- **El cursor está ligado a `sort` y `order`.** Si cambian, descarta las páginas cargadas y empieza sin `after`: un cursor de otro orden da 422.
- Si cambian los filtros o `q`, también hay que empezar de cero: incluye todos los parámetros en la `queryKey`.

### Empleados (`GET /employees`)

| Parámetro | Tipo | Efecto |
|---|---|---|
| `is_active` | `true` / `false` | Omitido: activos e inactivos |
| `email` | email | Coincidencia exacta |
| `q` | texto, 1 a 100 | Coincidencia parcial, sin distinguir mayúsculas, en nombre, apellido y email |
| `department_id` | UUID | Empleados de ese departamento |
| `manager_id` | UUID | Subordinados directos de ese jefe |
| `has_manager` | `true` / `false` | `false`: las raíces del organigrama |
| `job_title_id` | UUID | Empleados cuyo puesto **actual** es ese |
| `sort` | `last_name` (por defecto), `first_name`, `hire_date`, `created_at` | Orden |
| `order` | `asc` (por defecto), `desc` | Dirección |
| `after` | cursor | Página siguiente |

Los filtros se combinan. Un filtro por un id que no existe devuelve una página vacía, no un 404.

**Organigrama:** las raíces salen de `GET /employees?has_manager=false&is_active=true`. Ya no hace falta filtrarlas en el cliente. Si hay más de una, ofrece un selector. `GET /employees/{id}/tree` no cambió: sigue devolviendo `{employee, reports: [...]}` recursivo.

### Departamentos (`GET /departments`)

| Parámetro | Efecto |
|---|---|
| `q` | Coincidencia parcial en el nombre (1 a 100 caracteres) |
| `sort` | `name` (por defecto) o `created_at` |
| `order` | `asc` (por defecto) o `desc` |
| `after` | Página siguiente |

### Puestos (`GET /job-titles`)

**Sigue sin paginar**: devuelve el array completo, porque es un catálogo corto que los selects necesitan entero.

| Parámetro | Efecto |
|---|---|
| `q` | Coincidencia parcial en el nombre |
| `is_active` | Omitido: activos e inactivos |
| `sort` | Solo `name` |
| `order` | `asc` (por defecto) o `desc` |

### Búsqueda

- `q` debe tener entre 1 y 100 caracteres sin contar los espacios de los extremos. **Un `q` vacío da 422**: no lo envíes si el campo está en blanco.
- Usa *debounce* al escribir.
- `%` y `_` se buscan como texto normal, no como comodines.

### Valores inválidos

`sort`, `order`, `after` o `q` inválidos devuelven **422** con `error: "validation_error"`. Un cursor mal formado también.

## Departamentos

Todas las respuestas de departamento (lista, detalle, creación y edición) tienen la misma forma:

```json
{
  "id": "…",
  "name": "Tecnología",
  "manager_id": "…" ,
  "employee_count": 7,
  "created_at": "…"
}
```

- `employee_count` cuenta solo los empleados **activos** del departamento.
- El detalle ya no incluye la lista de empleados. Para mostrarla:

  ```
  GET /api/v1/employees?department_id=<id>&is_active=true
  ```

## Errores

Todos los errores tienen la misma forma: `{ "error": "...", "message": "...", "details": ... }`.

| HTTP | `error` | Cuándo | Qué hacer en el front |
|---|---|---|---|
| 401 | `invalid_credentials` | Email o contraseña incorrectos (el mensaje es el mismo en ambos casos) | Mostrarlo en el formulario. **No** cerrar sesión |
| 401 | `invalid_token` | Token ausente, caducado, inválido o de un usuario desactivado o inexistente | Borrar la sesión y enviar al login |
| 403 | `account_disabled` | La cuenta está desactivada y la contraseña es correcta | Mensaje de cuenta desactivada |
| 403 | `insufficient_permissions` | Falta un permiso. `details.required` lo indica | Mensaje, o ocultar la acción |
| 404 | `*_not_found` | El recurso no existe | |
| 409 | `user_email_exists` | El email ya está registrado | Marcar el campo email |
| 409 | `last_admin_required` | Dejaría el sistema sin administrador | Mensaje |
| 409 | otros | `email_already_exists`, `department_name_exists`, etc. | |
| 422 | `validation_error` | Entrada inválida. `details` es `[{loc, msg, type}]` | Marcar los campos según `loc` |
| 429 | `too_many_requests` | Demasiados intentos | Leer `Retry-After` (segundos), deshabilitar el botón y mostrar el tiempo |
| 500 | `internal_error` | Error del servidor | Mensaje genérico |

**Límites de intentos**

| Endpoint | Límite |
|---|---|
| Login | 5 contraseñas incorrectas por email en 15 minutos. Después, ese email queda bloqueado (429), incluso con la contraseña correcta |
| Login | 30 intentos por minuto por IP |
| Signup | 10 por hora por IP y 3 por hora por email |

Un login correcto reinicia el contador de fallos de ese email.

**Importante para el interceptor de axios:** el 401 `invalid_credentials` del login no debe disparar el cierre de sesión. Distingue por `error`, no solo por el código HTTP.

## CORS y entornos

- La API solo acepta peticiones del navegador desde los orígenes de su variable `CORS_ORIGINS`. **Añade ahí la URL del front** (la local y la de producción, separadas por coma, sin barra final). Sin eso el navegador bloquea todas las llamadas.
- Métodos permitidos: `GET`, `POST`, `PATCH` y `DELETE`. Headers permitidos: `Authorization` y `Content-Type`.
- No se usan cookies: el token va en el header, así que no hace falta `withCredentials`.
- La API tiene su bandera `APP_ENV` (`dev` o `production`). Haz lo mismo en el front con los modos de Vite:

  ```
  # .env.development
  VITE_API_URL=http://localhost:8010/api/v1

  # .env.production
  VITE_API_URL=https://basic-work-tree-api-production.up.railway.app/api/v1
  ```

- Documentación interactiva de la API: `/docs` (Swagger) y `/openapi.json`.

## Tipos de TypeScript

Conviene generarlos desde `/openapi.json` (por ejemplo con `openapi-typescript`). Estos son los que cambian o son nuevos:

```ts
type Page<T> = {
  items: T[];
  next_cursor: string | null;
};

type Permission =
  | "employees:read"
  | "employees:write"
  | "positions:write"
  | "job-titles:write"
  | "departments:write"
  | "users:write";

type AuthUser = {
  id: string; // UUID
  email: string;
  full_name: string | null;
  is_active: boolean;
  permissions: Permission[];
};

type AuthSession = {
  access_token: string;
  token_type: "bearer";
  expires_in: number; // segundos
  user: AuthUser;
};

type SignupRequest = { full_name: string; email: string; password: string };
type LoginRequest = { email: string; password: string };

type UserUpdate = {
  permissions?: Permission[];
  is_active?: boolean;
};

// Antes: DepartmentResponse sin employee_count, y DepartmentDetail con employees.
type DepartmentResponse = {
  id: string;
  name: string;
  manager_id: string | null;
  employee_count: number;
  created_at: string;
};

type ApiError = {
  error: string;
  message: string;
  details: unknown;
};
```

## Ejemplos

**Interceptores de axios**

```ts
import axios from "axios";

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

api.interceptors.request.use((config) => {
  const token = getToken(); // de tu store de sesión
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const code = error.response?.data?.error;
    // Un token inválido cierra la sesión. Las credenciales incorrectas del login, no.
    if (error.response?.status === 401 && code === "invalid_token") {
      clearSession();
      window.location.assign("/login");
    }
    if (error.response?.status === 429) {
      error.retryAfter = Number(error.response.headers["retry-after"] ?? 0);
    }
    return Promise.reject(error);
  },
);
```

**Lista paginada con TanStack Query**

```ts
const query = useInfiniteQuery({
  // Todos los parámetros en la clave: si cambian, se empieza de cero.
  queryKey: ["employees", { q, departmentId, sort, order }],
  queryFn: ({ pageParam }) =>
    api
      .get<Page<EmployeeResponse>>("/employees", {
        params: {
          q: q || undefined, // nunca enviar q vacío (422)
          department_id: departmentId,
          is_active: true, // explícito: omitirlo devuelve también los inactivos
          sort,
          order,
          after: pageParam,
        },
      })
      .then((r) => r.data),
  initialPageParam: undefined as string | undefined,
  getNextPageParam: (last) => last.next_cursor ?? undefined,
});

const employees = query.data?.pages.flatMap((p) => p.items) ?? [];
// query.hasNextPage / query.fetchNextPage() para «cargar más» o scroll infinito
```

**Raíces del organigrama**

```ts
api.get<Page<EmployeeResponse>>("/employees", {
  params: { has_manager: false, is_active: true },
});
```

## Pendiente en la API

Estos puntos afectan al front y todavía no están resueltos:

- **Los salarios son visibles para cualquier usuario registrado.** `employees:read` incluye `current_position.salary` y el historial de puestos. Como el registro es público, cualquiera que cree una cuenta los ve. Ocultarlos en la interfaz no protege nada: es una decisión pendiente en la API.
- **No hay endpoint para cambiar o recuperar la contraseña.**
- **No hay refresh token ni cierre de sesión en el servidor.** Un token vale hasta que caduca (12 horas) o hasta que se desactiva al usuario.

## Lista de tareas para el front

- [ ] Quitar Auth0 y sus variables.
- [ ] Pantallas de registro e inicio de sesión; guardar el `access_token`.
- [ ] Interceptor de axios con el token y el cierre de sesión solo con `invalid_token`.
- [ ] Pedir `GET /auth/me` al cargar la app y tras cambios de permisos.
- [ ] Mostrar u ocultar acciones según los permisos.
- [ ] Manejo de 429 con `Retry-After` en el login y el registro.
- [ ] Pasar `/employees` y `/departments` a `useInfiniteQuery` con `{items, next_cursor}`.
- [ ] Reiniciar la paginación al cambiar `sort`, `order`, filtros o `q`.
- [ ] No enviar `q` vacío; usar debounce.
- [ ] Enviar `is_active=true` donde antes se asumía por defecto (selects de puestos, listados).
- [ ] Departamentos: usar `employee_count`; cargar los empleados con `?department_id=`.
- [ ] Organigrama: raíces con `has_manager=false&is_active=true`.
- [ ] Pantalla de usuarios (`GET /users`, `PATCH /users/{id}`) para quien tenga `users:write`, con el caso `last_admin_required`.
- [ ] Añadir la URL del front a `CORS_ORIGINS` de la API.
- [ ] `VITE_API_URL` por modo de Vite (desarrollo y producción).
- [ ] Regenerar los tipos desde `/openapi.json`.
