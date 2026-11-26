"""Permisos de la API. Un usuario tiene una lista de estos textos (users.permissions)."""

EMPLOYEES_READ = "employees:read"
EMPLOYEES_WRITE = "employees:write"
POSITIONS_WRITE = "positions:write"
JOB_TITLES_WRITE = "job-titles:write"
DEPARTMENTS_WRITE = "departments:write"
USERS_WRITE = "users:write"

ALL_PERMISSIONS = (
    EMPLOYEES_READ,
    EMPLOYEES_WRITE,
    POSITIONS_WRITE,
    JOB_TITLES_WRITE,
    DEPARTMENTS_WRITE,
    USERS_WRITE,
)

# Lo único que recibe quien se registra solo. Los permisos NUNCA vienen del body del signup.
DEFAULT_PERMISSIONS = (EMPLOYEES_READ,)

# Quien tiene este permiso gestiona usuarios y permisos: es un "admin". El sistema siempre
# debe conservar al menos un usuario activo con él.
ADMIN_PERMISSION = USERS_WRITE
