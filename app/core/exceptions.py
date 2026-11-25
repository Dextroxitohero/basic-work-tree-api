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


class ConflictError(DomainError):
    """La operación choca con el estado actual."""


class UnauthenticatedError(DomainError):
    """No se sabe quién hace la petición."""


class ForbiddenError(DomainError):
    """Se sabe quién es, pero no tiene permiso."""


class ServiceUnavailableError(DomainError):
    """Un servicio externo no responde."""
