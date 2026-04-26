from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from audit_repository import fetch_audit_payload
from audit_support import build_deep_inspection
from gemini_explainer import generate_proxy_explanation
from models.api_models import DeepInspectionResponse


router = APIRouter()


@router.get("/inspection/deep/{audit_id}", response_model=DeepInspectionResponse)
def deep_inspection(audit_id: str):
    try:
        payload = fetch_audit_payload(audit_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found.") from exc

    response = build_deep_inspection(payload)
    for node in response.nodes:
        node.proxy_explanation = generate_proxy_explanation(
            feature_name=node.id,
            shap_importance=node.shap_importance,
            domain=response.domain,
        )
    return response
