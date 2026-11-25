from app.core.exceptions import ConflictError, NotFoundError


class DepartmentNotFoundError(NotFoundError):
    code = "department_not_found"
    message = "El departamento no existe"


class DepartmentNameExistsError(ConflictError):
    code = "department_name_exists"
    message = "Ya existe un departamento con ese nombre"
