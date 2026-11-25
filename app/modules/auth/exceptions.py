from app.core.exceptions import ForbiddenError, ServiceUnavailableError, UnauthenticatedError


class InvalidTokenError(UnauthenticatedError):
    code = "invalid_token"
    message = "Token ausente, expirado o inválido"


class InsufficientPermissionsError(ForbiddenError):
    code = "insufficient_permissions"
    message = "No tienes permiso para esta operación"


class AuthProviderUnavailableError(ServiceUnavailableError):
    code = "auth_provider_unavailable"
    message = "No se pudo contactar al proveedor de identidad"
