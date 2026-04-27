from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


load_dotenv()

from firebase_config import firebase_admin_configured, validate_firebase_environment  # noqa: E402
from routes import (  # noqa: E402
    audit_router,
    auth_router,
    certificate_router,
    explain_router,
    health_router,
    inspection_router,
)
from seed_sample_audit import ensure_sample_audits  # noqa: E402
from vertex_model import validate_vertex_environment, use_vertex_ai  # noqa: E402


def validate_runtime_configuration() -> None:
    if firebase_admin_configured():
        validate_firebase_environment()
    if use_vertex_ai():
        validate_vertex_environment()


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_runtime_configuration()
    ensure_sample_audits()
    yield


app = FastAPI(title="Unbiased AI Decision", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Unbiased AI Decision backend is running",
        "health_url": "/health",
        "audit_url": "/audit",
        "certificate_url": "/certificate/{audit_id}",
    }


app.include_router(health_router)
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(audit_router, tags=["audit"])
app.include_router(explain_router, tags=["explain"])
app.include_router(inspection_router, tags=["inspection"])
app.include_router(certificate_router, tags=["certificate"])
