import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


logger = logging.getLogger(__name__)


app = FastAPI(title="FairFlow AI", version="1.0.0")

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
