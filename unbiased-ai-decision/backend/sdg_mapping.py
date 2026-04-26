from __future__ import annotations

from typing import Any


SDG_TARGETS: dict[str, dict[str, Any]] = {
    "sdg_8_5": {
        "target": "SDG 8.5",
        "target_text": (
            "By 2030, achieve full and productive employment and decent work for all women and men, "
            "including for young people and persons with disabilities, and equal pay for work of equal value."
        ),
        "metric": "demographic_parity",
        "legal_threshold": {"operator": "<=", "value": 0.1},
    },
    "sdg_10_3": {
        "target": "SDG 10.3",
        "target_text": (
            "Ensure equal opportunity and reduce inequalities of outcome, including by eliminating discriminatory "
            "laws, policies and practices and promoting appropriate legislation, policies and action in this regard."
        ),
        "metric": "disparate_impact",
        "legal_threshold": {"operator": ">=", "value": 0.8},
    },
    "sdg_16_b": {
        "target": "SDG 16.b",
        "target_text": (
            "Promote and enforce non-discriminatory laws and policies for sustainable development."
        ),
        "metric": "equalized_odds",
        "legal_threshold": {"operator": "<=", "value": 0.1},
    },
}


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _passes_threshold(value: float, threshold: dict[str, Any]) -> bool:
    operator = threshold.get("operator", "<=")
    threshold_value = _coerce_float(threshold.get("value", 0))
    if operator == ">=":
        return value >= threshold_value
    if operator == "<=":
        return abs(value) <= threshold_value
    return False


def build_sdg_mapping(metrics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    response: dict[str, dict[str, Any]] = {}
    for key, config in SDG_TARGETS.items():
        metric_name = config["metric"]
        current_value = _coerce_float(metrics.get(metric_name, 0))
        pass_value = _passes_threshold(current_value, config["legal_threshold"])
        response[key] = {
            "target": config["target"],
            "target_text": config["target_text"],
            "metric": metric_name,
            "current_value": round(current_value, 4),
            "legal_threshold": config["legal_threshold"],
            "pass": pass_value,
        }
    return response


def all_sdg_targets_pass(mapping: dict[str, dict[str, Any]]) -> bool:
    return all(bool(row.get("pass")) for row in mapping.values())
