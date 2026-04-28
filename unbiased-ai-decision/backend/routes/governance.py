from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from audit_repository import fetch_audit_payload, fetch_user_history
from vertex_pipeline import store_audit_result
from workspace_support import build_governance_summary


router = APIRouter()


@router.post("/governance/auditor/{audit_id}")
def governance_auditor(audit_id: str):
    try:
        payload = fetch_audit_payload(audit_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        ) from exc

    history = fetch_user_history(payload.get("user_id", ""), limit=10)
    summary = build_governance_summary(payload, history)
    updated_payload = dict(payload)
    updated_payload["governance_summary"] = summary
    store_audit_result(updated_payload["user_id"], updated_payload, audit_id=audit_id)
    return summary
