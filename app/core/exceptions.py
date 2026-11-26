"""Categorías de error. Cada módulo define sus errores concretos heredando de una de ellas.

No saben nada de HTTP: la traducción a códigos de estado vive en error_handlers.py.
"""

from typing import Any


class DomainError(Exception):
    code = "domain_error"
    message = "Error de dominio"

    def __init__(self, message: str | None = None, *, details: Any = None) -> None:
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)


class NotFoundError(DomainError):
    """El recurso no existe."""


class InvalidInputError(DomainError):
    """Un valor de la petición es inválido y solo se puede comprobar fuera de Pydantic."""


class ConflictError(DomainError):
    """La operación choca con el estado actual."""


class UnauthenticatedError(DomainError):
    """No se sabe quién hace la petición."""


class ForbiddenError(DomainError):
    """Se sabe quién es, pero no tiene permiso."""


class TooManyRequestsError(DomainError):
    """El cliente superó el límite de intentos. retry_after son los segundos de espera."""

    code = "too_many_requests"
    message = "Demasiados intentos. Inténtalo de nuevo más tarde"

    def __init__(self, *, retry_after: int, message: str | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(message)
