from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from models.api_models import DeepInspectionEdge, DeepInspectionNode, DeepInspectionResponse
from schemas import DomainName, schema_for_domain
from sdg_mapping import all_sdg_targets_pass


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def compute_certificate_sha256(payload: dict[str, Any]) -> str:
    certificate_basis = {
        "organization_name": payload.get("organization_name"),
        "domain": payload.get("domain"),
        "fairness_metrics": payload.get("fairness_metrics"),
        "sdg_mapping": payload.get("sdg_mapping"),
        "bias_score": payload.get("bias_score"),
        "created_at": payload.get("created_at"),
    }
    encoded = json.dumps(
        certificate_basis,
        sort_keys=True,
        default=_json_default,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def attach_certificate_fields(payload: dict[str, Any]) -> dict[str, Any]:
    mapping = payload.get("sdg_mapping", {})
    certified_fair = all_sdg_targets_pass(mapping) and float(payload.get("bias_score", 0)) <= 30.0
    payload["certified_fair"] = certified_fair
    payload["certificate_sha256"] = compute_certificate_sha256(payload)
    return payload


def build_deep_inspection(payload: dict[str, Any]) -> DeepInspectionResponse:
    domain = payload.get("domain", "hiring")
    if domain not in ("hiring", "lending", "medical"):
        domain = "hiring"
    protected_attributes = {str(value) for value in schema_for_domain(domain)["protected_attributes"]}
    payload_attribute = str(payload.get("protected_attribute_used", "")).strip()
    if payload_attribute:
        protected_attributes.add(payload_attribute)
    shap_values = {
        row.get("feature"): float(row.get("value", 0))
        for row in payload.get("shap_values", [])
        if row.get("feature")
    }
    graph = payload.get("causal_graph_json", {})
    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])

    nodes = [
        DeepInspectionNode(
            id=str(node.get("id")),
            shap_importance=round(shap_values.get(str(node.get("id")), 0.0), 6),
            proxy_explanation=(
                f"{node.get('id')} may act as a proxy because it sits on a causal path linked to protected attributes."
                if str(node.get("id")) not in protected_attributes
                else f"{node.get('id')} is a protected attribute and should be monitored directly."
            ),
            is_protected_attribute=str(node.get("id")) in protected_attributes,
        )
        for node in raw_nodes
        if node.get("id") is not None
    ]
    edges = [
        DeepInspectionEdge(
            source=str(edge.get("source")),
            target=str(edge.get("target")),
            weight=float(edge.get("weight", 0)),
            is_proxy_edge=(
                str(edge.get("source")) in protected_attributes
                or str(edge.get("target")) in protected_attributes
            ),
        )
        for edge in raw_edges
        if edge.get("source") is not None and edge.get("target") is not None
    ]

    return DeepInspectionResponse(
        audit_id=str(payload.get("audit_id")),
        domain=domain,
        nodes=nodes,
        edges=edges,
        pathway_summary=payload.get("causal_pathway", "No strong causal pathway detected."),
    )
