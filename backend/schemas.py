from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MetricSet(BaseModel):
    disparate_impact: float
    stat_parity_diff: float
    equal_opp_diff: float
    avg_odds_diff: float
    pass_flags: dict[str, bool] = Field(default_factory=dict)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    organization: str = Field(min_length=2, max_length=255)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: UUID
    user_email: EmailStr


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    audit_id: UUID
    name: str
    gender: str
    ethnicity: str
    age: int
    years_experience: float
    education_level: str
    original_decision: bool
    mitigated_decision: bool | None = None
    bias_flagged: bool
    shap_values: dict[str, Any] | None = None
    counterfactual_result: dict[str, Any] | None = None
    skills: str | None = None
    previous_companies: str | None = None


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    created_at: datetime
    dataset_name: str
    total_candidates: int
    disparate_impact: float
    stat_parity_diff: float
    equal_opp_diff: float
    avg_odds_diff: float
    bias_detected: bool
    mitigation_applied: bool
    fairness_score: float
    flagged_candidates: int = 0
    gender_hire_rates: dict[str, float] = Field(default_factory=dict)
    ethnicity_hire_rates: dict[str, float] = Field(default_factory=dict)


class BiasReport(BaseModel):
    audit: AuditResponse
    metrics: MetricSet
    candidates: list[CandidateResponse]
    summary: dict[str, Any]


class CounterfactualRequest(BaseModel):
    candidate_id: UUID


class CounterfactualResponse(BaseModel):
    candidate_id: UUID
    original_decision: bool
    counterfactual_decision: bool
    bias_detected: bool
    confidence: float
    changed_attributes: list[str]


class MitigationResponse(BaseModel):
    audit_id: UUID
    original: MetricSet
    after_reweighing: MetricSet
    after_prejudice_remover: MetricSet
    after_equalized_odds: MetricSet
    fairness_score_before: float
    fairness_score_after: float
    mitigated_candidates: int


class MemoryHit(BaseModel):
    audit_id: UUID | None = None
    stage: str
    score: float
    memory_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditorDecisionResponse(BaseModel):
    audit_id: UUID
    state: str
    recommendation: str
    rationale: str
    actions: list[str] = Field(default_factory=list)
    recalled_memories: list[MemoryHit] = Field(default_factory=list)


class ProxyFinding(BaseModel):
    feature: str
    proxy_strength: float
    treatment_effect: float
    risk_score: float
    is_proxy: bool
    explanation: str


class TCAVConcept(BaseModel):
    concept: str
    tcav_score: float
    sensitivity: float
    prevalence: float
    direction: str
    summary: str


class DeepInspectionResponse(BaseModel):
    audit_id: UUID
    protected_attribute: str
    dag_edges: list[dict[str, str]] = Field(default_factory=list)
    proxy_findings: list[ProxyFinding] = Field(default_factory=list)
    tcav_concepts: list[TCAVConcept] = Field(default_factory=list)
    engine: str


class CertificateResponse(BaseModel):
    audit_id: UUID
    hash_algorithm: str
    report_hash: str
    epsilon: float
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
