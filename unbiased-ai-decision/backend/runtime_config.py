from __future__ import annotations

import os


_PLACEHOLDER_VALUES = {
    "your_gemini_api_key_here",
    "your_gcp_project_id",
    "gs://your-bucket-name",
    "gs://your-staging-bucket",
    "gs://your-model-bucket",
    "your_vertex_endpoint_id",
    "https://your-cloud-run-url.run.app",
    "your_firebase_web_api_key",
    "your_firebase_web_app_id",
    "your_sender_id",
    "your_firebase_project_id",
    "your-project.firebaseapp.com",
    "your-project.appspot.com",
}


def env_text(name: str) -> str:
    return os.getenv(name, "").strip()


def is_placeholder_value(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return False
    if normalized in _PLACEHOLDER_VALUES:
        return True
    if normalized.startswith("your_"):
        return True
    if "your-project" in normalized:
        return True
    return False


def has_real_env_value(name: str) -> bool:
    value = env_text(name)
    return bool(value) and not is_placeholder_value(value)
