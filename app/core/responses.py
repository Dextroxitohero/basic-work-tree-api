from typing import Any

from app.core.schemas import ErrorResponse


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Documenta en OpenAPI que esos códigos devuelven ErrorResponse."""
    # 401, 403 y 422 son posibles en todos los endpoints.
    return {code: {"model": ErrorResponse} for code in (401, 403, 422, *status_codes)}
