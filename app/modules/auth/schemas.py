from typing import Annotated, ClassVar, Literal
from uuid import UUID

from pydantic import AfterValidator, EmailStr, Field, SecretStr

from app.core.schemas import InputModel, OutputModel, PatchModel, text_field
from app.modules.auth.permissions import ALL_PERMISSIONS

# Los emails se guardan en minúsculas: Ana@x.com y ana@x.com son la misma cuenta.
Email = Annotated[EmailStr, AfterValidator(str.lower)]
FullName = Annotated[str, text_field(120)]
# SecretStr: si el objeto se imprime o se loguea por error, la contraseña sale como **********.
NewPassword = Annotated[SecretStr, Field(min_length=8, max_length=128)]
# El máximo evita que alguien envíe un texto enorme para hacer trabajar al hash.
LoginPassword = Annotated[SecretStr, Field(min_length=1, max_length=128)]

# Un permiso desconocido en el body da 422.
Permission = Literal[*ALL_PERMISSIONS]


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted(set(values))


class TokenPayload(OutputModel):
    """Claims del JWT que usa la API."""

    sub: UUID  # id del usuario
    email: str | None = None
    permissions: list[str] = []


class SignupRequest(InputModel):
    full_name: FullName
    email: Email
    password: NewPassword
    # No hay campo de permisos: extra="forbid" rechaza con 422 cualquier intento de enviarlos.


class LoginRequest(InputModel):
    email: Email
    password: LoginPassword


class AuthUser(OutputModel):
    id: UUID
    email: str
    full_name: str | None
    is_active: bool
    permissions: list[str]


class AuthSession(OutputModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # segundos hasta que caduca el token
    user: AuthUser


class UserUpdate(PatchModel):
    not_nullable: ClassVar[frozenset[str]] = frozenset({"permissions", "is_active"})

    permissions: Annotated[list[Permission], AfterValidator(_unique_sorted)] | None = None
    is_active: bool | None = None
