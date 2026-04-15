from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FairnessMetrics(BaseModel):
    demographic_parity: float
    equalized_odds: float
    individual_fairness: float
    calibration_error: float
    disparate_impact: float | None = None


class ShapFeatureImpact(BaseModel):
    feature: str
    value: float


class AuditResult(BaseModel):
    audit_id: str | None = None
    user_id: str
    model_name: str
    dataset_name: str
    bias_score: float
    fairness_metrics: FairnessMetrics
    shap_values: list[dict[str, Any]] = Field(default_factory=list)
    shap_top3: list[str] = Field(default_factory=list)
    causal_graph_json: dict[str, Any] = Field(default_factory=dict)
    demographic_parity: float
    equalized_odds: float
    individual_fairness: float
    calibration_error: float
    gemini_explanation: str = ""
    sdg_tag: str = "SDG 10.3"
    status: str = "completed"
    created_at: datetime | None = None
