from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from audit_repository import fetch_audit_payload
from vertex_pipeline import store_audit_result
from workspace_support import run_mitigation_analysis, run_synthetic_patch


router = APIRouter()


@router.post("/mitigate/{audit_id}")
def mitigate_audit(audit_id: str):
    try:
        payload = fetch_audit_payload(audit_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        ) from exc

    try:
        result, updated_records = run_mitigation_analysis(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    updated_payload = dict(payload)
    updated_payload["candidate_records"] = updated_records
    updated_payload["mitigation_results"] = result
    store_audit_result(updated_payload["user_id"], updated_payload, audit_id=audit_id)
    return result


@router.post("/mitigate/synthetic/{audit_id}")
def synthetic_patch(
    audit_id: str,
    target_attribute: str = Query(default="gender"),
):
    try:
        payload = fetch_audit_payload(audit_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        ) from exc

    try:
        result = run_synthetic_patch(payload, target_attribute=target_attribute)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    updated_payload = dict(payload)
    mitigation_results = dict(updated_payload.get("mitigation_results", {}))
    mitigation_results["synthetic_patch"] = result
    updated_payload["mitigation_results"] = mitigation_results
    store_audit_result(updated_payload["user_id"], updated_payload, audit_id=audit_id)
    return result
