from typing import Annotated, Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


def text_field(max_length: int) -> StringConstraints:
    """Restricciones de texto: quita espacios de los extremos y no acepta vacíos."""
    return StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)


class InputModel(BaseModel):
    """Base de los contratos de ENTRADA.

    extra="forbid" rechaza con 422 cualquier campo no declarado: un typo del cliente
    se detecta al momento en vez de ignorarse en silencio.
    """

    model_config = ConfigDict(extra="forbid")


class PatchModel(InputModel):
    """Base de los contratos PATCH.

    En un PATCH hay que distinguir tres casos:
      {}                     -> no tocar el campo
      {"manager_id": null}   -> borrar el valor
      {"manager_id": "..."}  -> cambiar el valor
    Pydantic guarda en model_fields_set qué campos envió el cliente, y el router usa
    model_dump(exclude_unset=True) para pasar solo esos al servicio.
    """

    # Campos que se pueden omitir, pero no enviar como null (son NOT NULL en la DB).
    # ClassVar: es configuración de la clase, no un campo del contrato.
    not_nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> Self:
        for name in sorted(self.not_nullable & self.model_fields_set):
            if getattr(self, name) is None:
                # Un ValueError dentro de un validator se convierte en un 422.
                raise ValueError(f"{name} no puede ser null")
        return self


class OutputModel(BaseModel):
    """Base de los contratos de SALIDA.

    from_attributes=True permite construir el schema desde un objeto ORM, leyendo atributos.
    """

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    """Todas las respuestas de error de la API tienen esta forma."""

    error: Annotated[str, Field(examples=["employee_not_found"])]
    message: str
    details: Any | None = None
