from app.core.exceptions import ConflictError, NotFoundError


class JobTitleNotFoundError(NotFoundError):
    code = "job_title_not_found"
    message = "El puesto no existe en el catálogo"


class JobTitleNameExistsError(ConflictError):
    code = "job_title_name_exists"
    message = "Ya existe un puesto con ese nombre"


class JobTitleInactiveError(ConflictError):
    code = "job_title_inactive"
    message = "El puesto está descontinuado y no se puede asignar"
