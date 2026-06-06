from .audit import router as audit_router
from .auth import router as auth_router
from .candidates import router as candidates_router
from .certificate import router as certificate_router
from .domain import router as domain_router
from .explain import router as explain_router
from .governance import router as governance_router
from .health import router as health_router
from .inspection import router as inspection_router
from .mitigation import router as mitigation_router

__all__ = [
    "audit_router",
    "auth_router",
    "candidates_router",
    "certificate_router",
    "domain_router",
    "explain_router",
    "governance_router",
    "health_router",
    "inspection_router",
    "mitigation_router",
]
