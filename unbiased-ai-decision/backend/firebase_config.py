from __future__ import annotations

import base64
import json
import os
from typing import Any

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials, firestore

from runtime_config import has_real_env_value


firebase_app = None
db = None
auth = firebase_auth
_firestore_connection_checked = False
_firestore_unavailable_reason: str | None = None


def firebase_admin_configured() -> bool:
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
    encoded_json = os.getenv("FIREBASE_CREDENTIALS_JSON", "").strip()

    if has_real_env_value("FIREBASE_CREDENTIALS_JSON"):
        return True

    if not service_account_path:
        return False

    if service_account_path == "./serviceAccountKey.json" and not os.path.exists(
        service_account_path
    ):
        return False

    return True


def _load_firebase_credential():
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
    encoded_json = os.getenv("FIREBASE_CREDENTIALS_JSON", "").strip()

    if service_account_path:
        if service_account_path == "./serviceAccountKey.json" and not os.path.exists(
            service_account_path
        ):
            service_account_path = ""
        elif not os.path.exists(service_account_path):
            raise RuntimeError(
                f"FIREBASE_SERVICE_ACCOUNT_PATH points to a missing file: {service_account_path}"
            )

    if service_account_path:
        return credentials.Certificate(service_account_path)

    if has_real_env_value("FIREBASE_CREDENTIALS_JSON"):
        try:
            decoded = base64.b64decode(encoded_json).decode("utf-8")
            payload = json.loads(decoded)
        except Exception as exc:
            raise RuntimeError(
                "FIREBASE_CREDENTIALS_JSON must be a base64-encoded Firebase service account JSON payload."
            ) from exc
        return credentials.Certificate(payload)

    if encoded_json:
        raise RuntimeError(
            "FIREBASE_CREDENTIALS_JSON is set but still contains a placeholder value."
        )

    if service_account_path:
        if not os.path.exists(service_account_path):
            raise RuntimeError(
                f"FIREBASE_SERVICE_ACCOUNT_PATH points to a missing file: {service_account_path}"
            )
        return credentials.Certificate(service_account_path)

    raise RuntimeError(
        "Firebase Admin credentials are required. Set FIREBASE_SERVICE_ACCOUNT_PATH or FIREBASE_CREDENTIALS_JSON."
    )


def validate_firebase_environment() -> None:
    if not firebase_admin_configured():
        raise RuntimeError(
            "Firebase Admin credentials are missing. Set FIREBASE_SERVICE_ACCOUNT_PATH or FIREBASE_CREDENTIALS_JSON."
        )


def mark_firestore_unavailable(reason: Exception | str) -> None:
    global db, _firestore_connection_checked, _firestore_unavailable_reason
    _firestore_connection_checked = True
    _firestore_unavailable_reason = str(reason)
    db = None


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
    if _firestore_unavailable_reason is not None:
        raise RuntimeError(_firestore_unavailable_reason)
    if db is None:
        require_firebase_app()
    if db is None:
        raise RuntimeError("Firestore failed to initialize.")
    return db


def firestore_available() -> bool:
    global _firestore_connection_checked

    if not firebase_admin_configured():
        return False

    if _firestore_unavailable_reason is not None:
        return False

    if _firestore_connection_checked:
        return True

    try:
        list(require_firestore().collections())
    except Exception as exc:
        mark_firestore_unavailable(exc)
        return False

    _firestore_connection_checked = True
    return True


def firebase_status() -> dict[str, Any]:
    if not firebase_admin_configured():
        return {
            "firestore": "not_configured",
            "auth": "not_configured",
            "details": "Firebase Admin credentials are not configured.",
        }

    firestore_state = "connected" if firestore_available() else "error"
    details = None if firestore_state == "connected" else _firestore_unavailable_reason

    try:
        require_firebase_app()
        auth_state = "ready"
    except Exception as exc:
        auth_state = "error"
        if details is None:
            details = str(exc)

    return {
        "firestore": firestore_state,
        "auth": auth_state,
        "details": details,
    }
