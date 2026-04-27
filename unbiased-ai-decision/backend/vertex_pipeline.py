from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import numpy as np
from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from audit_support import attach_certificate_fields
from bias_analyzer import analyze_bias, prepare_audit_dataset
from firebase_config import require_firestore
from local_audit_store import local_store_enabled, upsert_local_audit
from runtime_config import has_real_env_value
from schemas import DomainName
from vertex_model import (
    cleanup_bundle,
    predict_with_endpoint,
    train_register_and_deploy,
    use_vertex_ai,
    vertex_sdk_available,
)


def vertex_status() -> str:
    if not use_vertex_ai():
        return "disabled"
    if not vertex_sdk_available():
        return "not_configured"
    required = (
        has_real_env_value("VERTEX_PROJECT_ID"),
        has_real_env_value("VERTEX_REGION"),
        has_real_env_value("VERTEX_STAGING_BUCKET"),
        has_real_env_value("VERTEX_MODEL_BUCKET"),
    )
    return "ready" if all(required) else "not_configured"


def _local_predict(bundle, feature_frame) -> tuple[np.ndarray, np.ndarray]:
    predictions = np.asarray(bundle.pipeline.predict(feature_frame)).astype(int)
    probabilities = np.asarray(bundle.pipeline.predict_proba(feature_frame))[:, -1]
    return predictions, probabilities


def run_bias_analysis(
    dataset_path: str,
    domain: DomainName,
    audit_id: str,
    status_callback: Any | None = None,
) -> dict[str, Any]:
    prepared = prepare_audit_dataset(dataset_path, domain)
    bundle = train_register_and_deploy(prepared, audit_id)
    try:
        if status_callback is not None:
            status_callback("computing_metrics")
        if use_vertex_ai() and bundle.endpoint_name:
            predictions, probabilities = predict_with_endpoint(bundle.endpoint_name, prepared.feature_frame)
            analysis_backend = "vertex_endpoint"
        else:
            predictions, probabilities = _local_predict(bundle, prepared.feature_frame)
            analysis_backend = "local_random_forest"

        result = analyze_bias(
            prepared=prepared,
            trained_model=bundle.pipeline,
            predictions=predictions,
            probabilities=probabilities,
            model_family=bundle.model_family,
            analysis_backend=analysis_backend,
            vertex_endpoint_name=bundle.endpoint_name,
            stage_callback=status_callback,
        )
        result["vertex_model_name"] = bundle.vertex_model_name
        result["vertex_endpoint_name"] = bundle.endpoint_name
        result["artifact_uri"] = bundle.artifact_uri
        return result
    finally:
        cleanup_bundle(bundle)


def create_audit_record(user_id: str, audit_id: str | None, payload: dict[str, Any]) -> str:
    document_id = audit_id or str(uuid4())
    if local_store_enabled():
        upsert_local_audit(
            document_id,
            {
                "user_id": user_id,
                "status": "processing",
                "stage": "uploading",
                **payload,
            },
        )
        return document_id

    firestore_client = require_firestore()
    firestore_client.collection("audits").document(document_id).set(
        {
            "user_id": user_id,
            "status": "processing",
            "stage": "uploading",
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
            **payload,
        },
        merge=True,
    )
    return document_id


def update_audit_status(
    audit_id: str,
    stage: str,
    status: str = "processing",
    extra: dict[str, Any] | None = None,
) -> None:
    if local_store_enabled():
        upsert_local_audit(
            audit_id,
            {
                "status": status,
                "stage": stage,
                **(extra or {}),
            },
        )
        return

    firestore_client = require_firestore()
    firestore_client.collection("audits").document(audit_id).set(
        {
            "status": status,
            "stage": stage,
            "updated_at": SERVER_TIMESTAMP,
            **(extra or {}),
        },
        merge=True,
    )


def store_audit_result(user_id: str, result_dict: dict[str, Any], audit_id: str | None = None) -> str:
    document_id = audit_id or str(uuid4())
    payload = {
        "user_id": user_id,
        "organization_name": result_dict.get("organization_name", "FairFlow Demo Organization"),
        "model_name": result_dict.get("model_name", "Unnamed Model"),
        "dataset_name": result_dict.get("dataset_name", "uploaded_dataset.csv"),
        "domain": result_dict.get("domain", "hiring"),
        "model_family": result_dict.get("model_family", "unknown"),
        "analysis_backend": result_dict.get("analysis_backend", "local"),
        "bias_score": result_dict.get("bias_score", 0),
        "fairness_metrics": result_dict.get("fairness_metrics", {}),
        "shap_values": result_dict.get("shap_values", []),
        "shap_top3": result_dict.get("shap_top3", []),
        "causal_graph_json": result_dict.get("causal_graph_json", {}),
        "causal_pathway": result_dict.get("causal_pathway", ""),
        "demographic_parity": result_dict.get("demographic_parity", 0),
        "equalized_odds": result_dict.get("equalized_odds", 0),
        "individual_fairness": result_dict.get("individual_fairness", 0),
        "calibration_error": result_dict.get("calibration_error", 0),
        "sdg_tag": "SDG 10.3",
        "sdg_mapping": result_dict.get("sdg_mapping", {}),
        "gemini_explanation": result_dict.get("gemini_explanation", ""),
        "gemini_recommendations": result_dict.get("gemini_recommendations", []),
        "gemini_legal_risk": result_dict.get("gemini_legal_risk", ""),
        "gemini_audit_qa": result_dict.get("gemini_audit_qa", []),
        "jurisdiction_risks": result_dict.get("jurisdiction_risks", []),
        "candidate_flags": result_dict.get("candidate_flags", []),
        "counterfactuals": result_dict.get("counterfactuals", []),
        "status": result_dict.get("status", "completed"),
        "stage": result_dict.get("stage", "complete"),
        "vertex_model_name": result_dict.get("vertex_model_name"),
        "vertex_endpoint_name": result_dict.get("vertex_endpoint_name"),
        "artifact_uri": result_dict.get("artifact_uri"),
        "created_at": result_dict.get("created_at"),
    }
    payload = attach_certificate_fields(payload)

    if local_store_enabled():
        upsert_local_audit(document_id, payload)
        return document_id

    firestore_client = require_firestore()
    collection = firestore_client.collection("audits")
    document_reference = collection.document(audit_id) if audit_id else collection.document()
    document_reference.set(
        {
            **payload,
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
        }
        if audit_id is None
        else {
            **payload,
            "updated_at": SERVER_TIMESTAMP,
        },
        merge=bool(audit_id),
    )
    return document_reference.id
