from app.core.exceptions import ConflictError, NotFoundError


class EmployeeNotFoundError(NotFoundError):
    code = "employee_not_found"
    message = "El empleado no existe"


class EmailAlreadyExistsError(ConflictError):
    code = "email_already_exists"
    message = "Ya existe un empleado con ese email"


class EmployeeInactiveError(ConflictError):
    code = "employee_inactive"
    message = "El empleado está dado de baja"


class InactiveManagerError(ConflictError):
    code = "inactive_manager"
    message = "El jefe indicado está dado de baja"


class CircularManagerReferenceError(ConflictError):
    code = "circular_manager_reference"
    message = "Asignar ese jefe crearía un ciclo en la jerarquía"
