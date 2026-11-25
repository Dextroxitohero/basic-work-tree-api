from pydantic import BaseModel


class TokenPayload(BaseModel):
    """Claims del JWT que usa la API."""

    sub: str  # ID único del usuario en Auth0, p.ej. "auth0|abc123"
    email: str | None = None
    permissions: list[str] = []
