import logging
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from cors_config import get_allowed_origins
from database import Base, SessionLocal, engine
from domain_config import PRESET_DOMAIN_TEMPLATES
from models import DomainTemplate
from routers.audit import router as audit_router
from routers.auth import router as auth_router
from routers.candidates import router as candidates_router
from routers.governance import router as governance_router
from routers.inspection import router as inspection_router
from routers.mitigation import router as mitigation_router
from routers.domain import router as domain_router
from routers.extract import router as extract_router
from routers.demo import router as demo_router
from routers.jd_audit import router as jd_router

logger = logging.getLogger(__name__)

# ── Rate limiter (IP-based) ───────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


app = FastAPI(
    title="FairFlow AI",
    version="1.0.0",
    docs_url=None,   # Disable Swagger UI in production
    redoc_url=None,  # Disable ReDoc in production
)

# ── Rate limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)  # Enables @limiter.limit on all routers

# ── Security headers middleware ───────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store"

    # Access log
    logger.info(
        "[ACCESS] %s %s | status=%s | ip=%s | %dms",
        request.method,
        request.url.path,
        response.status_code,
        request.client.host if request.client else "unknown",
        duration_ms,
    )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    audit_columns = {column["name"] for column in inspector.get_columns("audits")}
    if "domain_config" not in audit_columns:
        try:
            with engine.begin() as connection:
                if engine.dialect.name == "postgresql":
                    connection.execute(
                        text("ALTER TABLE audits ADD COLUMN IF NOT EXISTS domain_config JSONB NOT NULL DEFAULT '{}'::jsonb")
                    )
                else:
                    connection.execute(
                        text("ALTER TABLE audits ADD COLUMN domain_config TEXT NOT NULL DEFAULT '{}'")
                    )
        except SQLAlchemyError as exc:
            logger.warning("Could not auto-migrate audits.domain_config column: %s", exc)

    with SessionLocal() as session:
        for template in PRESET_DOMAIN_TEMPLATES.values():
            existing = session.query(DomainTemplate).filter(DomainTemplate.domain == template.domain).first()
            payload = template.model_dump(mode="json")
            if existing:
                existing.display_name = template.display_name
                existing.config = payload
            else:
                session.add(
                    DomainTemplate(
                        domain=template.domain,
                        display_name=template.display_name,
                        config=payload,
                    )
                )
        session.commit()


@app.get("/")
def health_check():
    return {"status": "FairFlow AI running"}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(audit_router, prefix="/audit", tags=["audit"])
app.include_router(candidates_router, tags=["candidates"])
app.include_router(mitigation_router, tags=["mitigation"])
app.include_router(inspection_router, tags=["inspection"])
app.include_router(governance_router, tags=["governance"])
app.include_router(domain_router, prefix="/domain", tags=["domain"])
app.include_router(extract_router, tags=["extraction"])
app.include_router(demo_router, prefix="/demo", tags=["demo"])
app.include_router(
    jd_router, 
    tags=["jd-audit"]
)
