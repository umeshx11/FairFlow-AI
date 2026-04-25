from __future__ import annotations

from typing import Any

import pandas as pd


DECISION_COLUMN = "hired"
RISK_GAP_THRESHOLD = 0.15
INDICASA_DIMENSIONS = [
    "caste",
    "religion",
    "disability_status",
    "region",
    "dialect",
    "ethnicity",
]


def _selection_rates(df: pd.DataFrame, attribute: str, decision_column: str) -> dict[str, float]:
    rates: dict[str, float] = {}
    grouped = df.groupby(attribute)
    for group_value, group_rows in grouped:
        total = len(group_rows)
        if total == 0:
            continue
        hired_rate = float(group_rows[decision_column].astype(int).mean())
        rates[str(group_value)] = round(hired_rate, 4)
    return rates


def _intersectional_snapshot(df: pd.DataFrame, decision_column: str) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    if "caste" in df.columns and "region" in df.columns:
        grouped = (
            df.groupby(["caste", "region"])[decision_column]
            .mean()
            .sort_values(ascending=False)
        )
        for (caste, region), rate in grouped.head(5).items():
            snapshots.append(
                {
                    "intersection": f"{caste} + {region}",
                    "hire_rate": round(float(rate), 4),
                }
            )
    if "religion" in df.columns and "dialect" in df.columns:
        grouped = (
            df.groupby(["religion", "dialect"])[decision_column]
            .mean()
            .sort_values(ascending=False)
        )
        for (religion, dialect), rate in grouped.head(5).items():
            snapshots.append(
                {
                    "intersection": f"{religion} + {dialect}",
                    "hire_rate": round(float(rate), 4),
                }
            )
    return snapshots


def run_cultural_bias_scan(df: pd.DataFrame, decision_column: str = DECISION_COLUMN) -> dict[str, Any]:
    if decision_column not in df.columns:
        raise ValueError("Cultural scan requires a decision column.")

    normalized = df.copy()
    normalized[decision_column] = normalized[decision_column].astype(int)
    for column in normalized.columns:
        if normalized[column].dtype == object:
            normalized[column] = normalized[column].fillna("Unknown").astype(str).str.strip()

    findings: list[dict[str, Any]] = []
    for attribute in INDICASA_DIMENSIONS:
        if attribute not in normalized.columns:
            continue

        rates = _selection_rates(normalized, attribute, decision_column)
        if len(rates) <= 1:
            continue

        lowest_group = min(rates, key=rates.get)
        highest_group = max(rates, key=rates.get)
        rate_gap = round(float(rates[highest_group] - rates[lowest_group]), 4)
        high_risk = bool(rate_gap >= RISK_GAP_THRESHOLD)
        findings.append(
            {
                "attribute": attribute,
                "selection_rates": rates,
                "lowest_hire_rate_group": lowest_group,
                "highest_hire_rate_group": highest_group,
                "rate_gap": rate_gap,
                "high_risk": high_risk,
                "note": (
                    f"{attribute} gap={rate_gap:.4f}. "
                    f"Low group={lowest_group}, high group={highest_group}."
                ),
            }
        )

    findings.sort(key=lambda item: item["rate_gap"], reverse=True)
    high_risk_dimensions = [item["attribute"] for item in findings if item["high_risk"]]

    return {
        "engine": "indicasa-heuristic-v1",
        "dimensions": findings,
        "high_risk_count": len(high_risk_dimensions),
        "high_risk_dimensions": high_risk_dimensions,
        "intersectional_snapshot": _intersectional_snapshot(normalized, decision_column),
    }
