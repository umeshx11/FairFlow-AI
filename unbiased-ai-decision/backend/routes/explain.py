from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from audit_repository import fetch_audit_payload
from gemini_explainer import explain_flagged_candidate, stream_audit_answer
from models.api_models import (
    AuditQuestionRequest,
    AuditQuestionResponse,
    ExplainCandidateRequest,
    ExplainCandidateResponse,
)


router = APIRouter()


@router.post("/explain/candidate", response_model=ExplainCandidateResponse)
def explain_candidate(request: ExplainCandidateRequest):
    try:
        fetch_audit_payload(request.audit_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found.") from exc
    explanation = explain_flagged_candidate(request.candidate.model_dump(by_alias=True), request.domain)
    return ExplainCandidateResponse(explanation=explanation)


@router.post("/explain/audit-question/stream")
def stream_audit_question(request: AuditQuestionRequest):
    try:
        payload = fetch_audit_payload(request.audit_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found.") from exc

    def event_stream():
        for chunk in stream_audit_answer(payload, request.question):
            yield json.dumps(AuditQuestionResponse(chunk=chunk).model_dump()) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
