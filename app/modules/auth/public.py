"""Lo que otros módulos pueden usar de auth."""

from app.modules.auth.dependencies import require_permission

__all__ = ["require_permission"]
