from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ml.bias_detector import run_bias_detection
from utils import metric_payload


def _positive_rate_by_group(df: pd.DataFrame, attribute: str, decision_column: str) -> dict[str, float]:
    rates: dict[str, float] = {}
    for group, group_rows in df.groupby(attribute):
        total = len(group_rows)
        if total == 0:
            continue
        rates[str(group)] = float(group_rows[decision_column].astype(int).mean())
    return rates


def _safe_numeric(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
        if np.isnan(parsed):
            return default
        return parsed
    except Exception:
        return default


def generate_synthetic_counterfactual_patch(
    df: pd.DataFrame,
    *,
    target_attribute: str = "gender",
    decision_column: str = "hired",
    max_rows: int = 500,
) -> dict[str, Any]:
    if target_attribute not in df.columns:
        return {
            "engine": "vertex-style-fallback",
            "enabled": False,
            "reason": f"Column '{target_attribute}' not present in dataset.",
            "generated_rows": 0,
            "target_attribute": target_attribute,
            "metrics_before": metric_payload(run_bias_detection(df)),
            "metrics_after": metric_payload(run_bias_detection(df)),
            "preview": [],
        }

    normalized = df.copy()
    normalized[decision_column] = normalized[decision_column].astype(int)
    for column in normalized.columns:
        if normalized[column].dtype == object:
            normalized[column] = normalized[column].fillna("Unknown").astype(str).str.strip()
        else:
            normalized[column] = normalized[column].fillna(0)

    base_detection = run_bias_detection(normalized)
    base_metrics = metric_payload(base_detection)

    rates = _positive_rate_by_group(normalized, target_attribute, decision_column)
    if len(rates) <= 1:
        return {
            "engine": "vertex-style-fallback",
            "enabled": False,
            "reason": f"Not enough group diversity in '{target_attribute}'.",
            "generated_rows": 0,
            "target_attribute": target_attribute,
            "metrics_before": base_metrics,
            "metrics_after": base_metrics,
            "preview": [],
        }

    privileged_group = max(rates, key=rates.get)
    target_rate = rates[privileged_group]
    rng = np.random.default_rng(42)

    synthetic_rows: list[dict[str, Any]] = []
    for group, group_rows in normalized.groupby(target_attribute):
        group_key = str(group)
        if group_key == privileged_group:
            continue

        current_rate = rates.get(group_key, 0.0)
        if current_rate >= target_rate:
            continue

        group_total = len(group_rows)
        current_positive = int(group_rows[decision_column].sum())
        desired_positive = int(np.ceil(target_rate * group_total))
        rows_needed = max(0, desired_positive - current_positive)
        if rows_needed == 0:
            continue

        positive_pool = group_rows[group_rows[decision_column] == 1]
        source_pool = positive_pool if not positive_pool.empty else group_rows
        if source_pool.empty:
            continue

        sample_count = min(rows_needed, max_rows - len(synthetic_rows))
        if sample_count <= 0:
            break

        sampled = source_pool.sample(
            n=sample_count,
            replace=True,
            random_state=42,
        )
        for _, row in sampled.iterrows():
            synthetic = row.to_dict()
            synthetic[decision_column] = 1
            synthetic["name"] = f"SYNTH_{group_key}_{len(synthetic_rows) + 1}"
            if "years_experience" in synthetic:
                synthetic["years_experience"] = round(
                    max(0.0, _safe_numeric(synthetic["years_experience"]) + rng.normal(0.2, 0.35)),
                    2,
                )
            if "age" in synthetic:
                synthetic["age"] = int(
                    max(18, round(_safe_numeric(synthetic["age"], 18) + rng.normal(0, 1.2)))
                )
            synthetic_rows.append(synthetic)

    if not synthetic_rows:
        return {
            "engine": "vertex-style-fallback",
            "enabled": False,
            "reason": "No synthetic rows were needed to match target group selection rates.",
            "generated_rows": 0,
            "target_attribute": target_attribute,
            "metrics_before": base_metrics,
            "metrics_after": base_metrics,
            "preview": [],
        }

    patched_df = pd.concat([normalized, pd.DataFrame(synthetic_rows)], ignore_index=True)
    patched_detection = run_bias_detection(patched_df)
    patched_metrics = metric_payload(patched_detection)

    return {
        "engine": "vertex-style-fallback",
        "enabled": True,
        "target_attribute": target_attribute,
        "privileged_group": privileged_group,
        "target_positive_rate": round(float(target_rate), 4),
        "generated_rows": len(synthetic_rows),
        "metrics_before": base_metrics,
        "metrics_after": patched_metrics,
        "preview": synthetic_rows[:25],
    }
