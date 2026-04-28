from __future__ import annotations

import logging
import os


logger = logging.getLogger(__name__)

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://eco-crow-439708-k8.web.app",
    "https://eco-crow-439708-k8.firebaseapp.com",
)


def get_allowed_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
    if configured_origins:
        origins = [
            origin.strip().rstrip("/")
            for origin in configured_origins.split(",")
            if origin.strip()
        ]
        if origins:
            return origins
        logger.warning(
            "CORS_ALLOW_ORIGINS was set, but no valid origins were found. Falling back to defaults."
        )

    return list(DEFAULT_CORS_ORIGINS)
