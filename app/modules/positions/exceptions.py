from app.core.exceptions import ConflictError, NotFoundError


class NoActivePositionError(NotFoundError):
    code = "no_active_position"
    message = "El empleado no tiene un puesto activo"


class OverlappingPositionError(ConflictError):
    code = "overlapping_position"
    message = "Las fechas se solapan con otro puesto del empleado"
