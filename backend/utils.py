from collections import defaultdict
from typing import Any

import numpy as np

from models import Audit, Candidate


PASS_THRESHOLDS = {
    "disparate_impact": 0.8,
    "stat_parity_diff": 0.1,
    "equal_opp_diff": 0.1,
    "avg_odds_diff": 0.1,
}


def _safe_float(value: Any, *, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    if not np.isfinite(parsed):
        return fallback
    return parsed


def compute_pass_flags(metrics: dict[str, float]) -> dict[str, bool]:
    disparate_impact = _safe_float(metrics.get("disparate_impact", 0.0))
    stat_parity_diff = _safe_float(metrics.get("stat_parity_diff", 0.0))
    equal_opp_diff = _safe_float(metrics.get("equal_opp_diff", 0.0))
    avg_odds_diff = _safe_float(metrics.get("avg_odds_diff", 0.0))
    return {
        "disparate_impact": disparate_impact > PASS_THRESHOLDS["disparate_impact"],
        "stat_parity_diff": abs(stat_parity_diff) < PASS_THRESHOLDS["stat_parity_diff"],
        "equal_opp_diff": abs(equal_opp_diff) < PASS_THRESHOLDS["equal_opp_diff"],
        "avg_odds_diff": abs(avg_odds_diff) < PASS_THRESHOLDS["avg_odds_diff"],
    }


def calculate_fairness_score(metrics: dict[str, Any]) -> float:
    pass_flags = metrics.get("pass_flags") or compute_pass_flags(metrics)
    total_checks = len(pass_flags) or 1
    score = (sum(1 for passed in pass_flags.values() if passed) / total_checks) * 100
    return round(score, 2)


def metric_payload(metrics: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "disparate_impact": round(_safe_float(metrics.get("disparate_impact", 0.0)), 4),
        "stat_parity_diff": round(_safe_float(metrics.get("stat_parity_diff", 0.0)), 4),
        "equal_opp_diff": round(_safe_float(metrics.get("equal_opp_diff", 0.0)), 4),
        "avg_odds_diff": round(_safe_float(metrics.get("avg_odds_diff", 0.0)), 4),
    }
    payload["pass_flags"] = metrics.get("pass_flags") or compute_pass_flags(payload)
    return payload


def to_serializable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_serializable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_serializable(item) for item in value]
    if isinstance(value, tuple):
        return [to_serializable(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return _safe_float(value)
    if isinstance(value, float):
        return _safe_float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def serialize_candidate(candidate: Candidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "audit_id": candidate.audit_id,
        "name": candidate.name,
        "gender": candidate.gender,
        "ethnicity": candidate.ethnicity,
        "age": candidate.age,
        "years_experience": candidate.years_experience,
        "education_level": candidate.education_level,
        "original_decision": candidate.original_decision,
        "mitigated_decision": candidate.mitigated_decision,
        "bias_flagged": candidate.bias_flagged,
        "shap_values": to_serializable(candidate.shap_values),
        "counterfactual_result": to_serializable(candidate.counterfactual_result),
        "skills": candidate.skills,
        "previous_companies": candidate.previous_companies,
    }


def compute_group_hire_rates(candidates: list[Candidate], attribute: str) -> dict[str, float]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"hired": 0, "total": 0})
    for candidate in candidates:
        key = str(getattr(candidate, attribute))
        counts[key]["total"] += 1
        counts[key]["hired"] += int(candidate.original_decision)
    return {
        group: round(values["hired"] / values["total"], 4) if values["total"] else 0.0
        for group, values in counts.items()
    }


def serialize_audit(audit: Audit) -> dict[str, Any]:
    metrics = metric_payload(
        {
            "disparate_impact": audit.disparate_impact,
            "stat_parity_diff": audit.stat_parity_diff,
            "equal_opp_diff": audit.equal_opp_diff,
            "avg_odds_diff": audit.avg_odds_diff,
        }
    )
    candidates = audit.candidates or []
    return {
        "id": audit.id,
        "user_id": audit.user_id,
        "created_at": audit.created_at,
        "dataset_name": audit.dataset_name,
        "total_candidates": audit.total_candidates,
        "disparate_impact": metrics["disparate_impact"],
        "stat_parity_diff": metrics["stat_parity_diff"],
        "equal_opp_diff": metrics["equal_opp_diff"],
        "avg_odds_diff": metrics["avg_odds_diff"],
        "bias_detected": audit.bias_detected,
        "mitigation_applied": audit.mitigation_applied,
        "fairness_score": calculate_fairness_score(metrics),
        "flagged_candidates": sum(1 for candidate in candidates if candidate.bias_flagged),
        "gender_hire_rates": compute_group_hire_rates(candidates, "gender"),
        "ethnicity_hire_rates": compute_group_hire_rates(candidates, "ethnicity"),
    }


def rebuild_audit_rows(candidates: list[Candidate]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        base_row = dict(candidate.feature_payload or {})
        base_row.update(
            {
                "name": candidate.name,
                "gender": candidate.gender,
                "ethnicity": candidate.ethnicity,
                "age": candidate.age,
                "years_experience": candidate.years_experience,
                "education_level": candidate.education_level,
                "skills": candidate.skills or "",
                "previous_companies": candidate.previous_companies or "",
                "hired": int(candidate.original_decision),
            }
        )
        rows.append(to_serializable(base_row))
    return rows
