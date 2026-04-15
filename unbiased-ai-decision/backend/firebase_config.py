from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials, firestore


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FirebaseStatus:
    firestore: str
    auth: str
    details: str | None = None


def _load_firebase_credential():
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    encoded_json = os.getenv("FIREBASE_CREDENTIALS_JSON")

    if service_account_path:
        if not os.path.exists(service_account_path):
            raise FileNotFoundError(
                f"Firebase service account file was not found: {service_account_path}"
            )
        return credentials.Certificate(service_account_path)

    if encoded_json:
        decoded = base64.b64decode(encoded_json).decode("utf-8")
        payload = json.loads(decoded)
        return credentials.Certificate(payload)

    return credentials.ApplicationDefault()


def initialize_firebase():
    try:
        return firebase_admin.get_app()
    except ValueError:
        credential = _load_firebase_credential()
        return firebase_admin.initialize_app(credential)


def _build_clients():
    try:
        app = initialize_firebase()
        firestore_client = firestore.client(app=app)
        return app, firestore_client, firebase_auth
    except Exception as exc:
        logger.warning("Firebase initialization failed: %s", exc)
        return None, None, firebase_auth


firebase_app, db, auth = _build_clients()


def require_firestore():
    if db is None:
        raise RuntimeError(
            "Firestore is not initialized. Set FIREBASE_SERVICE_ACCOUNT_PATH or "
            "FIREBASE_CREDENTIALS_JSON before starting the backend."
        )
    return db


def firebase_status() -> dict[str, Any]:
    firestore_state = "connected"
    auth_state = "ready"
    detail: str | None = None

    if db is None:
        firestore_state = "not_configured"
        auth_state = "not_configured"
        detail = (
            "Set FIREBASE_SERVICE_ACCOUNT_PATH or FIREBASE_CREDENTIALS_JSON to enable Firebase services."
        )
    else:
        try:
            list(require_firestore().collections())
        except Exception as exc:
            firestore_state = "error"
            detail = str(exc)

    return {
        "firestore": firestore_state,
        "auth": auth_state,
        "details": detail,
    }
