from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from firebase_admin import firestore

from firebase_config import require_firestore
from local_audit_store import (
    fetch_local_audit_payload,
    list_local_audits,
    local_store_enabled,
    resolve_audit_ids,
)


def normalize_audit_payload(payload: dict[str, Any], document_id: str) -> dict[str, Any]:
    created_at = payload.get("created_at") or datetime.now(timezone.utc)
    return {
        "audit_id": document_id,
        "user_id": payload.get("user_id", ""),
        "organization_name": payload.get("organization_name", "FairFlow Demo Organization"),
        "model_name": payload.get("model_name", ""),
        "dataset_name": payload.get("dataset_name", ""),
        "domain": payload.get("domain", "hiring"),
        "model_family": payload.get("model_family", "unknown"),
        "analysis_backend": payload.get("analysis_backend", "local"),
        "bias_score": payload.get("bias_score", 0),
        "fairness_metrics": payload.get("fairness_metrics", {}),
        "shap_values": payload.get("shap_values", []),
        "shap_top3": payload.get("shap_top3", []),
        "causal_graph_json": payload.get("causal_graph_json", {}),
        "causal_pathway": payload.get("causal_pathway", ""),
        "demographic_parity": payload.get("demographic_parity", 0),
        "equalized_odds": payload.get("equalized_odds", 0),
        "individual_fairness": payload.get("individual_fairness", 0),
        "calibration_error": payload.get("calibration_error", 0),
        "gemini_explanation": payload.get("gemini_explanation", ""),
        "gemini_recommendations": payload.get("gemini_recommendations", []),
        "gemini_legal_risk": payload.get("gemini_legal_risk", ""),
        "gemini_audit_qa": payload.get("gemini_audit_qa", []),
        "jurisdiction_risks": payload.get("jurisdiction_risks", []),
        "candidate_flags": payload.get("candidate_flags", []),
        "counterfactuals": payload.get("counterfactuals", []),
        "sdg_tag": payload.get("sdg_tag", "SDG 10.3"),
        "sdg_mapping": payload.get("sdg_mapping", {}),
        "status": payload.get("status", "completed"),
        "stage": payload.get("stage", "complete"),
        "vertex_model_name": payload.get("vertex_model_name"),
        "vertex_endpoint_name": payload.get("vertex_endpoint_name"),
        "artifact_uri": payload.get("artifact_uri"),
        "certificate_sha256": payload.get("certificate_sha256", ""),
        "certified_fair": payload.get("certified_fair", False),
        "created_at": created_at,
    }


def fetch_audit_payload(audit_id: str) -> dict[str, Any]:
    if local_store_enabled():
        payload = fetch_local_audit_payload(audit_id)
        document_id = str(payload.get("audit_id") or audit_id)
        return normalize_audit_payload(payload, document_id)

    for candidate in resolve_audit_ids(audit_id):
        snapshot = require_firestore().collection("audits").document(candidate).get()
        if snapshot.exists:
            return normalize_audit_payload(snapshot.to_dict() or {}, snapshot.id)
    raise KeyError(audit_id)


def fetch_user_history(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    if local_store_enabled():
        return [
            normalize_audit_payload(item, str(item.get("audit_id") or ""))
            for item in list_local_audits(user_id, limit=limit)
        ]

    docs = (
        require_firestore()
        .collection("audits")
        .where("user_id", "==", user_id)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [normalize_audit_payload(snapshot.to_dict() or {}, snapshot.id) for snapshot in docs]
