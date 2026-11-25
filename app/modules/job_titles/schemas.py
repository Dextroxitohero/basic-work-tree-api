from datetime import datetime
from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import Field

from app.core.schemas import InputModel, OutputModel, PatchModel, text_field

# Annotated combina el tipo con sus validaciones; con un alias se reutiliza en varios schemas.
JobTitleName = Annotated[str, text_field(120)]
Description = Annotated[str, Field(max_length=1000)]


class JobTitleCreate(InputModel):
    name: JobTitleName
    description: Description | None = None


class JobTitleUpdate(PatchModel):
    not_nullable: ClassVar[frozenset[str]] = frozenset({"name", "is_active"})

    name: JobTitleName | None = None
    description: Description | None = None
    is_active: bool | None = None


class JobTitleResponse(OutputModel):
    id: UUID
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
