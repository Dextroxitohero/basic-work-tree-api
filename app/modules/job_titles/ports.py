"""Puertos: lo que el servicio necesita de fuera, sin saber quién lo implementa.

Un Protocol es "duck typing" verificable: cualquier clase con estos métodos lo cumple, sin
heredar de él. Por eso en los tests se puede pasar un repositorio falso en memoria.
"""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.modules.job_titles.models import JobTitle


class JobTitleStore(Protocol):
    async def get_by_id(self, job_title_id: UUID) -> JobTitle | None: ...
    async def list_all(self, *, is_active: bool) -> Sequence[JobTitle]: ...
    async def save(self, job_title: JobTitle) -> JobTitle: ...
