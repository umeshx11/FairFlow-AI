from __future__ import annotations

import os


DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


def get_gemini_model_name() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


def has_configured_gemini_key() -> bool:
    normalized = os.getenv("GEMINI_API_KEY", "").strip().lower()
    return bool(normalized) and normalized not in {
        "your-actual-key-here",
        "your-gemini-api-key-here",
    }
