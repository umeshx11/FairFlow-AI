from __future__ import annotations

import base64
import json
import os
from typing import Any

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials, firestore


firebase_app = None
db = None
auth = firebase_auth


def firebase_admin_configured() -> bool:
    return bool(
        os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
        or os.getenv("FIREBASE_CREDENTIALS_JSON", "").strip()
    )


def _load_firebase_credential():
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
    encoded_json = os.getenv("FIREBASE_CREDENTIALS_JSON", "").strip()

    if service_account_path:
        if not os.path.exists(service_account_path):
            raise RuntimeError(
                f"FIREBASE_SERVICE_ACCOUNT_PATH points to a missing file: {service_account_path}"
            )
        return credentials.Certificate(service_account_path)

    if encoded_json:
        try:
            decoded = base64.b64decode(encoded_json).decode("utf-8")
            payload = json.loads(decoded)
        except Exception as exc:
            raise RuntimeError(
                "FIREBASE_CREDENTIALS_JSON must be a base64-encoded Firebase service account JSON payload."
            ) from exc
        return credentials.Certificate(payload)

    raise RuntimeError(
        "Firebase Admin credentials are required. Set FIREBASE_SERVICE_ACCOUNT_PATH or FIREBASE_CREDENTIALS_JSON."
    )


def validate_firebase_environment() -> None:
    if not firebase_admin_configured():
        raise RuntimeError(
            "Firebase Admin credentials are missing. Set FIREBASE_SERVICE_ACCOUNT_PATH or FIREBASE_CREDENTIALS_JSON."
        )


def initialize_firebase():
    try:
        return firebase_admin.get_app()
    except ValueError:
        credential = _load_firebase_credential()
        return firebase_admin.initialize_app(credential)


def _build_clients():
    app = initialize_firebase()
    firestore_client = firestore.client(app=app)
    return app, firestore_client, firebase_auth


def require_firebase_app():
    global firebase_app, db
    if firebase_app is None or db is None:
        firebase_app, db, _ = _build_clients()
    return firebase_app


def require_firestore():
    global db
    if db is None:
        require_firebase_app()
    if db is None:
        raise RuntimeError("Firestore failed to initialize.")
    return db


def firebase_status() -> dict[str, Any]:
    if not firebase_admin_configured():
        return {
            "firestore": "not_configured",
            "auth": "not_configured",
            "details": "Firebase Admin credentials are not configured.",
        }

    try:
        list(require_firestore().collections())
        firestore_state = "connected"
        details = None
    except Exception as exc:
        firestore_state = "error"
        details = str(exc)

    return {
        "firestore": firestore_state,
        "auth": "ready" if firebase_app else "error",
        "details": details,
    }
