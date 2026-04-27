from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from audit_repository import fetch_audit_payload, fetch_user_history
from bias_analyzer import detect_available_protected_attributes
from gemini_explainer import generate_gemini_insights
from models.audit_result import AuditResult, FairnessMetrics
from schemas import DomainName
from vertex_pipeline import create_audit_record, run_bias_analysis, store_audit_result, update_audit_status


router = APIRouter()
TMP_DIR = Path(tempfile.gettempdir()) / "unbiased-ai-decision"
TMP_DIR.mkdir(parents=True, exist_ok=True)


def _audit_response(payload: dict) -> AuditResult:
    return AuditResult(
        audit_id=payload.get("audit_id"),
        user_id=payload["user_id"],
        organization_name=payload.get("organization_name", "FairFlow Demo Organization"),
        model_name=payload["model_name"],
        dataset_name=payload["dataset_name"],
        domain=payload.get("domain", "hiring"),
        protected_attribute_used=payload.get(
            "protected_attribute_used",
            payload.get("sensitive_attribute", "gender"),
        ),
        model_family=payload.get("model_family", "unknown"),
        analysis_backend=payload.get("analysis_backend", "local"),
        bias_score=payload["bias_score"],
        fairness_metrics=FairnessMetrics(**payload["fairness_metrics"]),
        shap_values=payload.get("shap_values", []),
        shap_top3=payload.get("shap_top3", []),
        causal_graph_json=payload.get("causal_graph_json", {}),
        demographic_parity=payload.get("demographic_parity", 0),
        equalized_odds=payload.get("equalized_odds", 0),
        individual_fairness=payload.get("individual_fairness", 0),
        calibration_error=payload.get("calibration_error", 0),
        gemini_explanation=payload.get("gemini_explanation", ""),
        gemini_recommendations=payload.get("gemini_recommendations", []),
        gemini_legal_risk=payload.get("gemini_legal_risk", ""),
        gemini_audit_qa=payload.get("gemini_audit_qa", []),
        jurisdiction_risks=payload.get("jurisdiction_risks", []),
        candidate_flags=payload.get("candidate_flags", []),
        counterfactuals=payload.get("counterfactuals", []),
        sdg_tag=payload.get("sdg_tag", "SDG 10.3"),
        sdg_mapping=payload.get("sdg_mapping", {}),
        status=payload.get("status", "completed"),
        stage=payload.get("stage", "complete"),
        vertex_endpoint_name=payload.get("vertex_endpoint_name"),
        certificate_sha256=payload.get("certificate_sha256", ""),
        certified_fair=payload.get("certified_fair", False),
        created_at=payload.get("created_at"),
    )


async def _persist_upload(upload_file: UploadFile, destination: Path) -> Path:
    contents = await upload_file.read()
    destination.write_bytes(contents)
    return destination


@router.post("/audit", response_model=AuditResult)
async def create_audit(
    dataset_file: UploadFile = File(...),
    model_file: UploadFile | None = File(None),
    model_name: str = Form(...),
    user_id: str = Form(...),
    domain: DomainName = Form(...),
    organization_name: str = Form("FairFlow Demo Organization"),
    audit_id: str | None = Form(None),
):
    if not dataset_file.filename or not dataset_file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="dataset_file must be a CSV upload.",
        )

    dataset_path = TMP_DIR / f"{uuid4()}-{dataset_file.filename}"
    await _persist_upload(dataset_file, dataset_path)
    try:
        uploaded_df = await run_in_threadpool(pd.read_csv, dataset_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse uploaded dataset: {exc}",
        ) from exc

    available_protected_attributes = detect_available_protected_attributes(uploaded_df)
    if not available_protected_attributes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No supported protected attribute was found in the uploaded CSV. "
                "Expected one of: gender, ethnicity, race, caste, religion, disability_status, region, age_group."
            ),
        )
    primary_protected_attribute = available_protected_attributes[0]

    document_id = create_audit_record(
        user_id,
        audit_id,
        {
            "organization_name": organization_name,
            "model_name": model_name,
            "dataset_name": dataset_file.filename,
            "domain": domain,
            "protected_attribute_used": primary_protected_attribute,
        },
    )
    update_audit_status(document_id, "uploading")

    def publish(stage: str, audit_status: str = "processing") -> None:
        update_audit_status(document_id, stage, audit_status)

    try:
        audit_result = await run_in_threadpool(
            run_bias_analysis,
            dataset_path=str(dataset_path),
            domain=domain,
            audit_id=document_id,
            protected_attribute=primary_protected_attribute,
            status_callback=publish,
        )
    except Exception as exc:
        update_audit_status(document_id, "failed", "failed", {"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Audit analysis failed: {exc}",
        ) from exc

    audit_result["organization_name"] = organization_name
    audit_result["model_name"] = model_name
    audit_result["dataset_name"] = dataset_file.filename
    audit_result["user_id"] = user_id
    audit_result["domain"] = domain
    audit_result["protected_attribute_used"] = primary_protected_attribute
    audit_result["status"] = "completed"
    audit_result["stage"] = "applying_mitigation"
    publish("applying_mitigation")
    gemini_insights = await run_in_threadpool(generate_gemini_insights, audit_result)
    audit_result["gemini_explanation"] = gemini_insights["explanation"]
    audit_result["gemini_recommendations"] = gemini_insights["recommendations"]
    audit_result["gemini_legal_risk"] = gemini_insights["legal_risk"]
    audit_result["gemini_audit_qa"] = gemini_insights["audit_qa"]
    audit_result["jurisdiction_risks"] = gemini_insights["jurisdiction_risks"]
    audit_result["stage"] = "complete"
    audit_result["created_at"] = datetime.now(timezone.utc)
    document_id = store_audit_result(user_id, audit_result, audit_id=document_id)

    payload = fetch_audit_payload(document_id)
    return _audit_response(payload)


@router.get("/audit/{audit_id}", response_model=AuditResult)
def get_audit(audit_id: str):
    try:
        payload = fetch_audit_payload(audit_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found.") from exc
    return _audit_response(payload)


@router.get("/audit/history/{user_id}")
def get_audit_history(user_id: str):
    return fetch_user_history(user_id, limit=20)
