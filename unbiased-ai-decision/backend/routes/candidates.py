from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from audit_repository import fetch_audit_payload
from workspace_support import candidate_page, find_candidate


router = APIRouter()


@router.get("/candidates/{audit_id}")
def get_candidates(
    audit_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str = Query(default=""),
    bias_status: str = Query(default="all"),
):
    try:
        payload = fetch_audit_payload(audit_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        ) from exc
    return candidate_page(
        payload,
        page=page,
        page_size=page_size,
        search=search,
        bias_status=bias_status,
    )


@router.get("/candidates/{audit_id}/{candidate_id}")
def get_candidate_detail(audit_id: str, candidate_id: str):
    try:
        payload = fetch_audit_payload(audit_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        ) from exc

    candidate = find_candidate(payload, candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )
    return candidate
