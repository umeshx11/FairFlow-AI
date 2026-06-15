import os

def has_configured_gemini_key() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") and os.getenv("GEMINI_API_KEY").strip())

def get_gemini_model_name() -> str:
    return os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-pro")
