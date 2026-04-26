from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from schemas import DomainName


AuditStage = Literal[
    "uploading",
    "computing_metrics",
    "generating_shap",
    "running_counterfactuals",
    "applying_mitigation",
    "complete",
    "failed",
]


class ThresholdModel(BaseModel):
    operator: str
    value: float


class SdgTargetResult(BaseModel):
    target: str
    target_text: str
    metric: str
    current_value: float
    legal_threshold: ThresholdModel
    pass_: bool = Field(alias="pass")

    model_config = {"populate_by_name": True}


class SdgMappingResponse(BaseModel):
    sdg_8_5: SdgTargetResult
    sdg_10_3: SdgTargetResult
    sdg_16_b: SdgTargetResult


class CandidateFlag(BaseModel):
    row_id: str
    protected_group: str
    sensitive_attribute: str
    predicted_decision: int
    approval_probability: float
    primary_drivers: list[str] = Field(default_factory=list)
    recommendation_seed: str = ""
    shap_values: list[dict[str, Any]] = Field(default_factory=list)
    counterfactual: dict[str, Any] = Field(default_factory=dict)


class CounterfactualChange(BaseModel):
    feature: str
    current_value: float
    suggested_value: float
    direction: str


class CounterfactualRecord(BaseModel):
    row_id: str
    current_probability: float
    suggested_changes: list[CounterfactualChange] = Field(default_factory=list)


class JurisdictionRisk(BaseModel):
    jurisdiction: str
    framework: str
    status: Literal["green", "amber", "red"]
    summary: str


class ExplainCandidateRequest(BaseModel):
    audit_id: str
    candidate: CandidateFlag
    domain: DomainName


class ExplainCandidateResponse(BaseModel):
    explanation: str


class AuditQuestionRequest(BaseModel):
    audit_id: str
    question: str


class AuditQuestionResponse(BaseModel):
    chunk: str


class DeepInspectionNode(BaseModel):
    id: str
    shap_importance: float = 0.0
    proxy_explanation: str = ""
    is_protected_attribute: bool = False


class DeepInspectionEdge(BaseModel):
    source: str
    target: str
    weight: float
    is_proxy_edge: bool


class DeepInspectionResponse(BaseModel):
    audit_id: str
    domain: DomainName
    nodes: list[DeepInspectionNode] = Field(default_factory=list)
    edges: list[DeepInspectionEdge] = Field(default_factory=list)
    pathway_summary: str


class FairnessCertificate(BaseModel):
    audit_id: str
    organization_name: str
    audit_date: datetime | None = None
    domain: DomainName
    fairness_metrics: dict[str, float]
    sdg_mapping: SdgMappingResponse
    certificate_sha256: str
    certified_fair: bool
    badge_label: str
