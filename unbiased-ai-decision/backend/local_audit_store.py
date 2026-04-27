from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from firebase_config import firebase_admin_configured


STORE_PATH = Path(tempfile.gettempdir()) / "unbiased-ai-decision" / "audits.json"
_STORE_LOCK = Lock()


def local_store_enabled() -> bool:
    return not firebase_admin_configured()


def resolve_audit_ids(audit_id: str) -> list[str]:
    if audit_id == "sample_hiring_audit":
        return ["sample_hiring_audit", "sample_audit"]
    if audit_id == "sample_audit":
        return ["sample_audit", "sample_hiring_audit"]
    return [audit_id]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _coerce_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str) and value.strip():
        return value
    return _utc_now().isoformat()


def _load_state() -> dict[str, Any]:
    if not STORE_PATH.exists():
        return {"audits": {}}
    try:
        decoded = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"audits": {}}
    if not isinstance(decoded, dict):
        return {"audits": {}}
    audits = decoded.get("audits")
    if not isinstance(audits, dict):
        return {"audits": {}}
    return {"audits": audits}


def _save_state(state: dict[str, Any]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(
        json.dumps(state, indent=2, sort_keys=True, default=_serialize_json) + "\n",
        encoding="utf-8",
    )


def upsert_local_audit(
    audit_id: str,
    payload: dict[str, Any],
    *,
    merge: bool = True,
) -> dict[str, Any]:
    with _STORE_LOCK:
        state = _load_state()
        audits = state["audits"]
        current = audits.get(audit_id, {}) if merge else {}
        record = {**current, **payload}
        record["audit_id"] = audit_id
        record["created_at"] = _coerce_timestamp(
            payload.get("created_at") or current.get("created_at")
        )
        record["updated_at"] = _coerce_timestamp(payload.get("updated_at"))
        audits[audit_id] = record
        _save_state(state)
        return record.copy()


def local_audit_exists(audit_id: str) -> bool:
    with _STORE_LOCK:
        state = _load_state()
        audits = state["audits"]
        return any(candidate in audits for candidate in resolve_audit_ids(audit_id))


def fetch_local_audit_payload(audit_id: str) -> dict[str, Any]:
    with _STORE_LOCK:
        state = _load_state()
        audits = state["audits"]
        for candidate in resolve_audit_ids(audit_id):
            payload = audits.get(candidate)
            if isinstance(payload, dict):
                return payload.copy()
    raise KeyError(audit_id)


def list_local_audits(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    def sort_key(payload: dict[str, Any]) -> str:
        created_at = payload.get("created_at")
        return created_at if isinstance(created_at, str) else ""

    with _STORE_LOCK:
        state = _load_state()
        items = [
            payload.copy()
            for payload in state["audits"].values()
            if isinstance(payload, dict) and payload.get("user_id") == user_id
        ]
    items.sort(key=sort_key, reverse=True)
    return items[:limit]
