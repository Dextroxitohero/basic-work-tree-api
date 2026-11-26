from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthenticatedError,
)


class InvalidTokenError(UnauthenticatedError):
    code = "invalid_token"
    message = "Token ausente, expirado o inválido"


class InvalidCredentialsError(UnauthenticatedError):
    """Mismo código y mensaje si falla el email o la contraseña: no revela cuál de los dos."""

    code = "invalid_credentials"
    message = "Email o contraseña incorrectos"


class InsufficientPermissionsError(ForbiddenError):
    code = "insufficient_permissions"
    message = "No tienes permiso para esta operación"


class AccountDisabledError(ForbiddenError):
    code = "account_disabled"
    message = "La cuenta está desactivada"


class UserEmailExistsError(ConflictError):
    code = "user_email_exists"
    message = "Ya existe un usuario con ese email"


class UserNotFoundError(NotFoundError):
    code = "user_not_found"
    message = "El usuario no existe"


class LastAdminError(ConflictError):
    code = "last_admin_required"
    message = "Debe quedar al menos un administrador activo"
