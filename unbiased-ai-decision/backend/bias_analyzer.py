from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import LabelEncoder

from schemas import DomainName, schema_for_domain
from sdg_mapping import build_sdg_mapping

try:
    import shap
except Exception:
    shap = None


NON_FEATURE_COLUMNS = {"id", "name", "full_name", "candidate_id", "organization_name"}
PROTECTED_ATTRIBUTE_PRIORITY = [
    "gender",
    "ethnicity",
    "race",
    "caste",
    "religion",
    "disability_status",
    "region",
    "age_group",
]


@dataclass(slots=True)
class PreparedDataset:
    domain: DomainName
    raw: pd.DataFrame
    normalized: pd.DataFrame
    feature_frame: pd.DataFrame
    labels: np.ndarray
    feature_columns: list[str]
    target_column: str
    sensitive_column: str
    protected_binary: np.ndarray
    protected_mapping: dict[int, str]
    organization_name: str


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _coerce_binary_label(series: pd.Series) -> pd.Series:
    lowered = series.astype(str).str.strip().str.lower()
    mapped = lowered.replace(
        {
            "1": 1,
            "0": 0,
            "true": 1,
            "false": 0,
            "yes": 1,
            "no": 0,
            "approved": 1,
            "rejected": 0,
            "hire": 1,
            "hired": 1,
            "treated": 1,
            "untreated": 0,
        }
    )
    numeric = pd.to_numeric(mapped, errors="coerce")
    if numeric.notna().sum() != len(series):
        factorized, _ = pd.factorize(lowered)
        numeric = pd.Series(factorized, index=series.index)
    return (numeric > 0).astype(int)


def _binarize_sensitive(series: pd.Series) -> tuple[np.ndarray, dict[int, str]]:
    clean = series.fillna("Unknown")
    if pd.api.types.is_numeric_dtype(clean):
        threshold = float(clean.median())
        binary = (clean.astype(float) > threshold).astype(int).to_numpy()
        return binary, {0: f"<= {threshold:.2f}", 1: f"> {threshold:.2f}"}

    encoded = clean.astype(str).str.strip()
    top_groups = list(encoded.value_counts().index[:2])
    if len(top_groups) == 1:
        top_groups.append("Other")
    binary = encoded.apply(lambda value: 1 if value == top_groups[0] else 0).to_numpy()
    return binary, {0: str(top_groups[1]), 1: str(top_groups[0])}


def _normalize_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    normalized = dataframe.copy()
    for column in normalized.columns:
        if normalized[column].dtype == object:
            normalized[column] = normalized[column].fillna("Unknown").astype(str).str.strip()
        else:
            normalized[column] = normalized[column].fillna(0)
    return normalized


def detect_available_protected_attributes(df: pd.DataFrame) -> list[str]:
    normalized_columns = {str(column).strip().lower(): str(column).strip() for column in df.columns}
    detected: list[str] = []
    for candidate in PROTECTED_ATTRIBUTE_PRIORITY:
        matched = normalized_columns.get(candidate.lower())
        if matched:
            detected.append(matched)
    return detected


def _encode_features(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    encoded = df.copy()
    for column in feature_columns:
        if encoded[column].dtype == object:
            encoder = LabelEncoder()
            encoded[column] = encoder.fit_transform(encoded[column].fillna("Unknown").astype(str))
    return encoded


def _row_label(row: pd.Series, row_index: int) -> str:
    for key in ("candidate_id", "patient_id", "applicant_id", "id", "name", "full_name"):
        if key in row and str(row[key]).strip():
            return str(row[key])
    return f"row-{row_index + 1}"


def prepare_audit_dataset(
    dataset_path: str,
    domain: DomainName,
    protected_attribute: str | None = None,
) -> PreparedDataset:
    dataframe = pd.read_csv(dataset_path)
    dataframe.columns = [column.strip() for column in dataframe.columns]
    schema = schema_for_domain(domain)
    target_column = str(schema["target"])
    available_protected_attributes = detect_available_protected_attributes(dataframe)
    schema_protected_attributes = [str(column) for column in schema["protected_attributes"]]
    sensitive_column = (
        protected_attribute
        or next((column for column in available_protected_attributes if column in dataframe.columns), None)
        or next((column for column in schema_protected_attributes if column in dataframe.columns), None)
    )
    if sensitive_column is None:
        raise ValueError(
            "The uploaded CSV does not include any supported protected attributes. "
            "Expected one of: gender, ethnicity, race, caste, religion, disability_status, region, age_group."
        )

    non_protected_schema_features = [
        str(column)
        for column in schema["features"]
        if str(column) not in schema_protected_attributes
    ]
    feature_candidates = list(
        dict.fromkeys(
            [
                *non_protected_schema_features,
                *[column for column in schema_protected_attributes if column in dataframe.columns],
                sensitive_column,
            ]
        )
    )
    feature_columns = [column for column in feature_candidates if column in dataframe.columns]
    required_columns = set(non_protected_schema_features) | {target_column, sensitive_column}
    missing = sorted(required_columns.difference(dataframe.columns))
    if missing:
        raise ValueError(
            f"The uploaded CSV does not match the {domain} schema. Missing columns: {', '.join(missing)}"
        )

    normalized = _normalize_dataframe(dataframe)
    normalized[target_column] = _coerce_binary_label(normalized[target_column])
    protected_binary, protected_mapping = _binarize_sensitive(normalized[sensitive_column])
    encoded = _encode_features(normalized, feature_columns)
    feature_frame = encoded[feature_columns].copy()
    labels = normalized[target_column].to_numpy(dtype=int)
    organization_name = (
        str(normalized["organization_name"].iloc[0]).strip()
        if "organization_name" in normalized.columns
        else "FairFlow Demo Organization"
    )

    return PreparedDataset(
        domain=domain,
        raw=dataframe,
        normalized=normalized,
        feature_frame=feature_frame,
        labels=labels,
        feature_columns=feature_columns,
        target_column=target_column,
        sensitive_column=sensitive_column,
        protected_binary=protected_binary,
        protected_mapping=protected_mapping,
        organization_name=organization_name,
    )


def _group_stats(y_true: np.ndarray, y_pred: np.ndarray, group: np.ndarray, target_group: int) -> dict[str, float]:
    mask = group == target_group
    if mask.sum() == 0:
        return {"selection_rate": 0.0, "tpr": 0.0, "fpr": 0.0}
    group_true = y_true[mask]
    group_pred = y_pred[mask]
    positives = group_true == 1
    negatives = group_true == 0
    return {
        "selection_rate": float(np.mean(group_pred == 1)),
        "tpr": float(np.mean(group_pred[positives] == 1)) if positives.any() else 0.0,
        "fpr": float(np.mean(group_pred[negatives] == 1)) if negatives.any() else 0.0,
    }


def _compute_individual_fairness(feature_frame: pd.DataFrame, predictions: np.ndarray) -> float:
    if len(feature_frame) < 2:
        return 1.0
    neighbors = min(6, len(feature_frame))
    nn = NearestNeighbors(n_neighbors=neighbors)
    nn.fit(feature_frame)
    _, indices = nn.kneighbors(feature_frame)
    mismatches: list[float] = []
    for row_index, row_neighbors in enumerate(indices):
        for neighbor_index in row_neighbors[1:]:
            mismatches.append(abs(int(predictions[row_index]) - int(predictions[neighbor_index])))
    if not mismatches:
        return 1.0
    return round(1.0 - float(np.mean(mismatches)), 4)


def compute_fairness_metrics(
    labels: np.ndarray,
    predictions: np.ndarray,
    probabilities: np.ndarray,
    protected_binary: np.ndarray,
    feature_frame: pd.DataFrame,
) -> dict[str, Any]:
    privileged = _group_stats(labels, predictions, protected_binary, 1)
    unprivileged = _group_stats(labels, predictions, protected_binary, 0)
    privileged_selection = privileged["selection_rate"] or 1e-9
    demographic_parity = unprivileged["selection_rate"] - privileged["selection_rate"]
    equalized_odds = 0.5 * (
        (unprivileged["tpr"] - privileged["tpr"]) + (unprivileged["fpr"] - privileged["fpr"])
    )
    disparate_impact = unprivileged["selection_rate"] / privileged_selection
    calibration_error = float(brier_score_loss(labels, probabilities))
    individual_fairness = _compute_individual_fairness(feature_frame, predictions)
    return {
        "demographic_parity": round(float(demographic_parity), 4),
        "equalized_odds": round(float(equalized_odds), 4),
        "individual_fairness": round(individual_fairness, 4),
        "calibration_error": round(calibration_error, 4),
        "disparate_impact": round(float(disparate_impact), 4),
    }


def calculate_bias_score(metrics: dict[str, Any]) -> float:
    parity_penalty = min(1.0, abs(_safe_float(metrics.get("demographic_parity"))) / 0.5)
    odds_penalty = min(1.0, abs(_safe_float(metrics.get("equalized_odds"))) / 0.5)
    impact_penalty = min(1.0, abs(1 - _safe_float(metrics.get("disparate_impact", 1.0))))
    calibration_penalty = min(1.0, _safe_float(metrics.get("calibration_error")))
    individual_penalty = 1 - min(1.0, _safe_float(metrics.get("individual_fairness", 1.0)))
    weighted = (
        0.30 * parity_penalty
        + 0.25 * odds_penalty
        + 0.20 * impact_penalty
        + 0.15 * calibration_penalty
        + 0.10 * individual_penalty
    )
    return round(float(weighted * 100), 2)


def compute_shap_summary(model: Any, feature_frame: pd.DataFrame) -> tuple[list[dict[str, float]], list[str]]:
    try:
        if shap is None:
            raise RuntimeError("shap is not installed")
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(feature_frame)
        values = np.array(shap_values[-1] if isinstance(shap_values, list) else shap_values)
        if values.ndim == 3:
            values = values[:, :, -1]
        mean_abs = np.abs(values).mean(axis=0)
    except Exception:
        inner_model = getattr(model, "named_steps", {}).get("model", model)
        if hasattr(inner_model, "feature_importances_"):
            mean_abs = np.asarray(inner_model.feature_importances_)
        else:
            mean_abs = np.zeros(feature_frame.shape[1], dtype=float)
    rows = [
        {"feature": feature, "value": round(float(mean_abs[index]), 6)}
        for index, feature in enumerate(feature_frame.columns)
    ]
    rows.sort(key=lambda item: item["value"], reverse=True)
    return rows[:10], [row["feature"] for row in rows[:3]]


def build_causal_graph(
    feature_frame: pd.DataFrame,
    protected_binary: np.ndarray,
    target_column: str,
    sensitive_column: str,
    shap_top3: list[str],
) -> tuple[dict[str, Any], str]:
    nodes = [{"id": sensitive_column}, {"id": target_column}]
    edges: list[dict[str, Any]] = []
    pathway = "No strong causal proxy pathway detected."
    protected_numeric = protected_binary.astype(float)
    for feature in shap_top3:
        if feature not in feature_frame.columns:
            continue
        correlation = abs(np.corrcoef(feature_frame[feature].astype(float), protected_numeric)[0, 1])
        if np.isnan(correlation):
            correlation = 0.0
        nodes.append({"id": feature})
        edges.append({"source": sensitive_column, "target": feature, "weight": round(float(correlation), 4)})
        edges.append({"source": feature, "target": target_column, "weight": round(float(max(correlation, 0.1)), 4)})
        if correlation >= 0.1 and pathway == "No strong causal proxy pathway detected.":
            pathway = f"{sensitive_column} -> {feature} -> {target_column}"
    deduped_nodes = list({node["id"]: node for node in nodes}.values())
    return {"nodes": deduped_nodes, "edges": edges}, pathway


def build_counterfactuals(
    prepared: PreparedDataset,
    predictions: np.ndarray,
    probabilities: np.ndarray,
    shap_top3: list[str],
) -> list[dict[str, Any]]:
    counterfactuals: list[dict[str, Any]] = []
    negative_indices = [index for index, prediction in enumerate(predictions) if int(prediction) == 0]
    for row_index in negative_indices[:5]:
        row = prepared.normalized.iloc[row_index]
        changes = []
        for feature in shap_top3:
            if feature not in prepared.feature_frame.columns:
                continue
            series = prepared.feature_frame[feature].astype(float)
            current_value = float(prepared.feature_frame.iloc[row_index][feature])
            median_value = float(series.median())
            if current_value == median_value:
                continue
            changes.append(
                {
                    "feature": feature,
                    "current_value": round(current_value, 4),
                    "suggested_value": round(median_value, 4),
                    "direction": "increase" if median_value > current_value else "decrease",
                }
            )
            if len(changes) == 2:
                break
        if not changes:
            continue
        counterfactuals.append(
            {
                "row_id": _row_label(row, row_index),
                "current_probability": round(float(probabilities[row_index]), 4),
                "suggested_changes": changes,
            }
        )
    return counterfactuals


def build_candidate_flags(
    prepared: PreparedDataset,
    predictions: np.ndarray,
    probabilities: np.ndarray,
    shap_values: list[dict[str, Any]],
    counterfactuals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    counterfactual_by_row = {row["row_id"]: row for row in counterfactuals}
    ranked_indices = np.argsort(probabilities)
    flags: list[dict[str, Any]] = []
    for row_index in ranked_indices:
        if len(flags) >= 5:
            break
        if int(predictions[row_index]) == 1 and probabilities[row_index] > 0.35:
            continue
        row = prepared.normalized.iloc[int(row_index)]
        group_value = prepared.protected_mapping.get(int(prepared.protected_binary[row_index]), "Unknown")
        row_id = _row_label(row, int(row_index))
        flags.append(
            {
                "row_id": row_id,
                "protected_group": group_value,
                "sensitive_attribute": prepared.sensitive_column,
                "predicted_decision": int(predictions[row_index]),
                "approval_probability": round(float(probabilities[row_index]), 4),
                "primary_drivers": [item["feature"] for item in shap_values[:3]],
                "recommendation_seed": (
                    "Review this decision with protected-attribute proxies masked before the final action."
                ),
                "shap_values": shap_values[:5],
                "counterfactual": counterfactual_by_row.get(row_id, {}),
            }
        )
    return flags


def analyze_bias(
    prepared: PreparedDataset,
    trained_model: Any,
    predictions: np.ndarray,
    probabilities: np.ndarray,
    model_family: str,
    analysis_backend: str,
    vertex_endpoint_name: str | None = None,
    stage_callback: Any | None = None,
) -> dict[str, Any]:
    if stage_callback is not None:
        stage_callback("generating_shap")
    shap_values, shap_top3 = compute_shap_summary(trained_model, prepared.feature_frame)
    causal_graph_json, causal_pathway = build_causal_graph(
        prepared.feature_frame,
        prepared.protected_binary,
        prepared.target_column,
        prepared.sensitive_column,
        shap_top3,
    )
    fairness_metrics = compute_fairness_metrics(
        prepared.labels,
        predictions,
        probabilities,
        prepared.protected_binary,
        prepared.feature_frame,
    )
    if stage_callback is not None:
        stage_callback("running_counterfactuals")
    counterfactuals = build_counterfactuals(prepared, predictions, probabilities, shap_top3)
    candidate_flags = build_candidate_flags(prepared, predictions, probabilities, shap_values, counterfactuals)
    return {
        "organization_name": prepared.organization_name,
        "domain": prepared.domain,
        "model_family": model_family,
        "analysis_backend": analysis_backend,
        "bias_score": calculate_bias_score(fairness_metrics),
        "fairness_metrics": fairness_metrics,
        "shap_values": shap_values,
        "shap_top3": shap_top3,
        "causal_graph_json": causal_graph_json,
        "causal_pathway": causal_pathway,
        "demographic_parity": fairness_metrics["demographic_parity"],
        "equalized_odds": fairness_metrics["equalized_odds"],
        "individual_fairness": fairness_metrics["individual_fairness"],
        "calibration_error": fairness_metrics["calibration_error"],
        "disparate_impact": fairness_metrics["disparate_impact"],
        "candidate_flags": candidate_flags,
        "counterfactuals": counterfactuals,
        "sdg_mapping": build_sdg_mapping(fairness_metrics),
        "protected_attribute_used": prepared.sensitive_column,
        "target_column": prepared.target_column,
        "sensitive_attribute": prepared.sensitive_column,
        "sensitive_groups": prepared.protected_mapping,
        "dataset_name": Path("dataset.csv").name,
        "row_count": int(len(prepared.normalized)),
        "column_count": int(len(prepared.normalized.columns)),
        "vertex_endpoint_name": vertex_endpoint_name,
    }
