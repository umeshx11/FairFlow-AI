from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter

from firebase_config import firebase_status
from gemini_explainer import gemini_sdk_available
from runtime_config import has_real_env_value
from vertex_pipeline import vertex_status


router = APIRouter()


@router.get("/health")
def health_check():
    firebase_services = firebase_status()
    gemini_state = (
        "ready"
        if has_real_env_value("GEMINI_API_KEY") and gemini_sdk_available()
        else "not_configured"
    )
    return {
        "status": "ok",
        "version": "1.0.0",
        "services": {
            "firestore": firebase_services["firestore"],
            "vertex": vertex_status(),
            "gemini": gemini_state,
            "auth": firebase_services["auth"],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": {
            "firebase": firebase_services.get("details"),
        },
    }
