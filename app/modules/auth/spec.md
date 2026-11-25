# Módulo `auth`

Responde dos preguntas: quién eres (autenticación) y qué puedes hacer (autorización). La API no guarda usuarios ni contraseñas: Auth0 emite el JWT y aquí se valida. Para desarrollo hay un modo local.

## Archivos

| Archivo | Contenido |
|---|---|
| `verifier.py` | `TokenVerifier` (Protocol) y `get_token_verifier`, que elige según `AUTH_MODE` |
| `auth0.py` | `Auth0TokenVerifier` |
| `local.py` | `LocalTokenVerifier`, `ADMIN` y `create_token` |
| `admin_token.py` | Comando que imprime un token de admin |
| `dependencies.py` | `get_current_user` y `require_permission` |
| `schemas.py` | `TokenPayload` |
| `exceptions.py` | Errores de autenticación y permisos |
| `public.py` | `require_permission`, lo único que usan otros módulos |

## Flujo

1. `HTTPBearer` extrae el token de `Authorization: Bearer <token>`.
2. `get_current_user` lo pasa al `TokenVerifier`.
3. El verificador activo valida el token (`Auth0TokenVerifier` usa la clave pública de Auth0, JWKS).
4. `require_permission("...")` comprueba el claim `permissions`.

## Validaciones del token (Auth0)

| Qué | Cómo |
|---|---|
| Firma | Clave pública de Auth0, según el `kid` del token |
| Algoritmo | Solo `RS256`; el que declara el token no decide |
| Audiencia (`aud`) | Igual a `AUTH0_AUDIENCE` |
| Emisor (`iss`) | Igual a `https://{AUTH0_DOMAIN}/` |
| Expiración (`exp`) | Obligatoria y vigente |
| Sujeto (`sub`) | Obligatorio |

`PyJWKClient` guarda las claves en caché y las vuelve a pedir si Auth0 las rota. Como usa HTTP síncrono, se ejecuta en otro hilo para no bloquear el event loop.

## Modo local

Solo para desarrollo. Se activa con `AUTH_MODE=local`; por defecto es `auth0`.

| Aspecto | Comportamiento |
|---|---|
| Firma | `HS256` con `LOCAL_JWT_SECRET` (mínimo 32 caracteres, sin valor por defecto) |
| Emisor | `local-dev`; también se validan audiencia, `exp` y `sub` |
| Usuario | `admin@example.com`, con todos los permisos |
| Vigencia | 12 horas |
| Arranque | Sin secreto la app no arranca; con él muestra un aviso |

En modo `auth0`, un token local se rechaza, y al revés.

## Permisos

| Permiso | Permite |
|---|---|
| `employees:read` | Todos los GET |
| `employees:write` | Crear, editar y dar de baja empleados |
| `positions:write` | Asignar puestos |
| `job-titles:write` | Crear y editar el catálogo de puestos |
| `departments:write` | Crear y editar departamentos |

`employees:read` incluye los salarios de todos los empleados.

## Errores

| Situación | HTTP | Código |
|---|---|---|
| Token ausente o inválido | 401 | `invalid_token` |
| Falta el permiso | 403 | `insufficient_permissions` (con `details.required`) |
| Auth0 no responde | 503 | `auth_provider_unavailable` |

## Cambiar de proveedor

En `verifier.py`, crea una clase con `async def verify(self, token: str) -> TokenPayload` y devuélvela en `get_token_verifier`. Los tests hacen lo mismo con `dependency_overrides`.
