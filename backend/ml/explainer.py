from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import shap


PROXY_FEATURES = {"zip_code", "university_name", "company_name", "previous_companies"}


def _extract_candidate_shap_values(shap_values: Any, candidate_index: int) -> np.ndarray:
    if isinstance(shap_values, list):
        if len(shap_values) == 0:
            return np.array([])
        if len(shap_values) == 1:
            return np.array(shap_values[0][candidate_index])
        return np.array(shap_values[-1][candidate_index])

    values = np.array(shap_values)
    if values.ndim == 3:
        return values[candidate_index, :, -1]
    if values.ndim == 2:
        return values[candidate_index]
    return np.array(values)


def explain_candidate(model, X, candidate_index: int, feature_names: list[str]) -> dict[str, Any]:
    feature_frame = X if isinstance(X, pd.DataFrame) else pd.DataFrame(X, columns=feature_names)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(feature_frame)
    candidate_shap = _extract_candidate_shap_values(shap_values, candidate_index)

    feature_values = feature_frame.iloc[candidate_index]
    explanation_rows = [
        {
            "feature": feature,
            "value": float(feature_values[feature]) if np.issubdtype(type(feature_values[feature]), np.number) else feature_values[feature],
            "shap_value": round(float(candidate_shap[index]), 6),
        }
        for index, feature in enumerate(feature_names)
    ]
    explanation_rows.sort(key=lambda item: abs(item["shap_value"]), reverse=True)

    top_positive = sorted(
        [row for row in explanation_rows if row["shap_value"] > 0],
        key=lambda item: item["shap_value"],
        reverse=True,
    )[:5]
    top_negative = sorted(
        [row for row in explanation_rows if row["shap_value"] < 0],
        key=lambda item: item["shap_value"],
    )[:5]

    if explanation_rows:
        importance_threshold = np.percentile([abs(row["shap_value"]) for row in explanation_rows], 75)
    else:
        importance_threshold = 0.0

    proxy_flags = [
        row["feature"]
        for row in explanation_rows
        if row["feature"] in PROXY_FEATURES and abs(row["shap_value"]) >= importance_threshold
    ]

    waterfall_data = [
        {
            "feature": row["feature"],
            "value": row["value"],
            "shap_value": row["shap_value"],
        }
        for row in explanation_rows
    ]

    strongest_positive = top_positive[0]["feature"] if top_positive else "none"
    strongest_negative = top_negative[0]["feature"] if top_negative else "none"
    reasoning_log = (
        "Candidate decision explanation: "
        f"strongest positive contributor={strongest_positive}; "
        f"strongest negative contributor={strongest_negative}. "
        + (
            f"Potential proxy discrimination risk via {', '.join(proxy_flags)}."
            if proxy_flags
            else "No high-importance proxy feature exceeded the risk threshold."
        )
    )

    return {
        "top_5_positive": top_positive,
        "top_5_negative": top_negative,
        "waterfall_data": waterfall_data,
        "proxy_flags": proxy_flags,
        "reasoning_log": reasoning_log,
    }
