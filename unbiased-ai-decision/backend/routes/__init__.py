from .audit import router as audit_router
from .auth import router as auth_router
from .certificate import router as certificate_router
from .explain import router as explain_router
from .health import router as health_router
from .inspection import router as inspection_router

__all__ = [
    "audit_router",
    "auth_router",
    "certificate_router",
    "explain_router",
    "health_router",
    "inspection_router",
]
