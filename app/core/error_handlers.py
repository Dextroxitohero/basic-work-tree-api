"""Traduce excepciones a respuestas HTTP. Es el único sitio que relaciona dominio y HTTP."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.exceptions import (
    ConflictError,
    DomainError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
    TooManyRequestsError,
    UnauthenticatedError,
)
from app.core.schemas import ErrorResponse

logger = logging.getLogger(__name__)

_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    InvalidInputError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    UnauthenticatedError: status.HTTP_401_UNAUTHORIZED,
    ForbiddenError: status.HTTP_403_FORBIDDEN,
    TooManyRequestsError: status.HTTP_429_TOO_MANY_REQUESTS,
}


def _response(
    status_code: int, error: ErrorResponse, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(jsonable_encoder(error), status_code=status_code, headers=headers)


async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    status_code = next(
        (code for cls, code in _STATUS_BY_ERROR.items() if isinstance(exc, cls)),
        status.HTTP_400_BAD_REQUEST,
    )
    # El estándar HTTP exige este header en las respuestas 401.
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    if isinstance(exc, TooManyRequestsError):
        headers = {"Retry-After": str(exc.retry_after)}  # cuántos segundos esperar
    return _response(
        status_code,
        ErrorResponse(error=exc.code, message=exc.message, details=exc.details),
        headers,
    )


async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Solo campos útiles: se omite "input" para no devolver al cliente datos sensibles.
    details = [{key: err[key] for key in ("loc", "msg", "type")} for err in exc.errors()]
    return _response(
        422,
        ErrorResponse(
            error="validation_error", message="La petición no es válida", details=details
        ),
    )


async def handle_http_error(_: Request, exc: HTTPException) -> JSONResponse:
    """Errores del propio framework: ruta inexistente (404), método no permitido (405)..."""
    return _response(
        exc.status_code,
        ErrorResponse(error="http_error", message=str(exc.detail)),
        exc.headers,
    )


async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    # El detalle va al log, nunca al cliente: podría filtrar información interna.
    logger.error("Error no controlado", exc_info=exc)
    return _response(
        500, ErrorResponse(error="internal_error", message="Error interno del servidor")
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(HTTPException, handle_http_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
