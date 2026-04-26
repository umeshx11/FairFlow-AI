from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from fairlearn.metrics import MetricFrame, selection_rate
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from utils import compute_pass_flags, metric_payload

try:
    from aif360.datasets import BinaryLabelDataset
    from aif360.metrics import BinaryLabelDatasetMetric, ClassificationMetric

    AIF360_AVAILABLE = True
except Exception:
    BinaryLabelDataset = None
    BinaryLabelDatasetMetric = None
    ClassificationMetric = None
    AIF360_AVAILABLE = False


LABEL_COLUMN = "hired"
PROTECTED_ATTRIBUTE = "gender"
NON_FEATURE_COLUMNS = {"name"}
COUNTERFACTUAL_PROTECTED_ATTRIBUTES = [
    "gender",
    "ethnicity",
    "caste",
    "religion",
    "disability_status",
    "region",
    "dialect",
]

POSITIVE_LABEL_TOKENS = {
    "1",
    "true",
    "t",
    "yes",
    "y",
    "hired",
    "selected",
    "accept",
    "accepted",
}
NEGATIVE_LABEL_TOKENS = {
    "0",
    "false",
    "f",
    "no",
    "n",
    "rejected",
    "reject",
    "not_hired",
    "not_selected",
    "declined",
}


def _normalize_label_token(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _normalize_hired_column(series: pd.Series) -> pd.Series:
    numeric_series = pd.to_numeric(series, errors="coerce")
    if numeric_series.notna().all():
        if not numeric_series.isin([0, 1]).all():
            invalid_values = sorted(set(numeric_series[~numeric_series.isin([0, 1])].tolist()))[:5]
            raise ValueError(
                "Column 'hired' must be binary. Supported values include "
                "0/1, yes/no, true/false. "
                f"Found unsupported numeric values: {invalid_values}"
            )
        return numeric_series.astype(int)

    normalized_tokens = series.map(_normalize_label_token)
    mapped = normalized_tokens.map(
        lambda token: 1
        if token in POSITIVE_LABEL_TOKENS
        else 0
        if token in NEGATIVE_LABEL_TOKENS
        else np.nan
    )
    if mapped.isna().any():
        invalid_tokens = sorted(set(normalized_tokens[mapped.isna()].tolist()))[:5]
        raise ValueError(
            "Column 'hired' must be binary. Supported values include "
            "0/1, yes/no, true/false, hired/rejected. "
            f"Found unsupported values: {invalid_tokens}"
        )
    return mapped.astype(int)


def _select_test_size(y: pd.Series) -> int | None:
    class_count = int(y.nunique())
    if len(y) < 6 or class_count < 2:
        return None
    min_class_count = int(y.value_counts().min())
    if min_class_count < 2:
        return None

    test_size = max(1, int(round(len(y) * 0.2)))
    if test_size < class_count:
        test_size = class_count
    if test_size >= len(y):
        return None
    return test_size


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [column.strip() for column in normalized.columns]
    for column in normalized.columns:
        if normalized[column].dtype == object:
            normalized[column] = normalized[column].fillna("Unknown").astype(str).str.strip()
        else:
            normalized[column] = normalized[column].fillna(0)

    if PROTECTED_ATTRIBUTE in normalized.columns:
        normalized[PROTECTED_ATTRIBUTE] = (
            normalized[PROTECTED_ATTRIBUTE]
            .astype(str)
            .str.strip()
            .str.lower()
            .replace(
                {
                    "m": "Male",
                    "male": "Male",
                    "man": "Male",
                    "f": "Female",
                    "female": "Female",
                    "woman": "Female",
                }
            )
        )
        normalized[PROTECTED_ATTRIBUTE] = normalized[PROTECTED_ATTRIBUTE].replace(
            {"Male": "Male", "Female": "Female"}
        )
        normalized[PROTECTED_ATTRIBUTE] = normalized[PROTECTED_ATTRIBUTE].apply(
            lambda value: value if value in {"Male", "Female"} else "Female"
        )

    if LABEL_COLUMN in normalized.columns:
        normalized[LABEL_COLUMN] = _normalize_hired_column(normalized[LABEL_COLUMN])

    return normalized


def encode_categorical_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, LabelEncoder]]:
    encoded = df.copy()
    encoders: dict[str, LabelEncoder] = {}
    for column in encoded.columns:
        if column == LABEL_COLUMN:
            continue
        if encoded[column].dtype == object:
            encoder = LabelEncoder()
            encoded[column] = encoder.fit_transform(encoded[column].astype(str))
            encoders[column] = encoder
    return encoded, encoders


def build_binary_label_dataset(encoded_df: pd.DataFrame, labels: np.ndarray | None = None):
    if not AIF360_AVAILABLE:
        return None

    dataset_df = encoded_df.copy()
    if labels is not None:
        dataset_df[LABEL_COLUMN] = labels.astype(int)

    return BinaryLabelDataset(
        favorable_label=1,
        unfavorable_label=0,
        df=dataset_df,
        label_names=[LABEL_COLUMN],
        protected_attribute_names=[PROTECTED_ATTRIBUTE],
    )


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def _group_rates(y_true: np.ndarray, y_pred: np.ndarray, protected: np.ndarray, group_value: int) -> dict[str, float]:
    mask = protected == group_value
    group_true = y_true[mask]
    group_pred = y_pred[mask]

    positives = group_true == 1
    negatives = group_true == 0

    selection = _safe_divide(np.sum(group_pred == 1), len(group_pred))
    true_positive_rate = _safe_divide(np.sum((group_pred == 1) & positives), np.sum(positives))
    false_positive_rate = _safe_divide(np.sum((group_pred == 1) & negatives), np.sum(negatives))

    return {
        "selection_rate": selection,
        "true_positive_rate": true_positive_rate,
        "false_positive_rate": false_positive_rate,
    }


def fallback_metrics(encoded_features: pd.DataFrame, y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    protected = encoded_features[PROTECTED_ATTRIBUTE].to_numpy()
    privileged = _group_rates(y_true, y_pred, protected, 1)
    unprivileged = _group_rates(y_true, y_pred, protected, 0)

    selection_frame = MetricFrame(
        metrics=selection_rate,
        y_true=y_true,
        y_pred=y_pred,
        sensitive_features=protected,
    )
    selection_by_group = selection_frame.by_group.to_dict()

    raw_metrics = {
        "disparate_impact": _safe_divide(unprivileged["selection_rate"], privileged["selection_rate"]),
        "stat_parity_diff": unprivileged["selection_rate"] - privileged["selection_rate"],
        "equal_opp_diff": unprivileged["true_positive_rate"] - privileged["true_positive_rate"],
        "avg_odds_diff": 0.5
        * (
            (unprivileged["false_positive_rate"] - privileged["false_positive_rate"])
            + (unprivileged["true_positive_rate"] - privileged["true_positive_rate"])
        ),
        "group_selection_rates": {str(key): round(float(value), 4) for key, value in selection_by_group.items()},
    }
    raw_metrics["pass_flags"] = compute_pass_flags(raw_metrics)
    return metric_payload(raw_metrics) | {"group_selection_rates": raw_metrics["group_selection_rates"]}


def compute_fairness_metrics(encoded_features: pd.DataFrame, y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    if not AIF360_AVAILABLE:
        return fallback_metrics(encoded_features, y_true, y_pred)

    try:
        dataset_df = encoded_features.copy()
        dataset_df[LABEL_COLUMN] = y_true.astype(int)
        original_dataset = build_binary_label_dataset(dataset_df)
        predicted_dataset = original_dataset.copy(deepcopy=True)
        predicted_dataset.labels = y_pred.astype(int).reshape(-1, 1)

        metric_dataset = BinaryLabelDatasetMetric(
            predicted_dataset,
            privileged_groups=[{PROTECTED_ATTRIBUTE: 1}],
            unprivileged_groups=[{PROTECTED_ATTRIBUTE: 0}],
        )
        classification_metric = ClassificationMetric(
            original_dataset,
            predicted_dataset,
            privileged_groups=[{PROTECTED_ATTRIBUTE: 1}],
            unprivileged_groups=[{PROTECTED_ATTRIBUTE: 0}],
        )

        raw_metrics = {
            "disparate_impact": float(metric_dataset.disparate_impact()),
            "stat_parity_diff": float(metric_dataset.statistical_parity_difference()),
            "equal_opp_diff": float(classification_metric.equal_opportunity_difference()),
            "avg_odds_diff": float(classification_metric.average_odds_difference()),
        }
        raw_metrics["pass_flags"] = compute_pass_flags(raw_metrics)
        return metric_payload(raw_metrics)
    except Exception:
        return fallback_metrics(encoded_features, y_true, y_pred)


def run_bias_detection(df: pd.DataFrame) -> dict[str, Any]:
    normalized_df = normalize_dataframe(df)
    if LABEL_COLUMN not in normalized_df.columns:
        raise ValueError("Dataset must include a 'hired' column.")
    if PROTECTED_ATTRIBUTE not in normalized_df.columns:
        raise ValueError("Dataset must include a 'gender' column.")

    encoded_df, encoders = encode_categorical_columns(normalized_df)
    feature_columns = [column for column in encoded_df.columns if column not in {LABEL_COLUMN, *NON_FEATURE_COLUMNS}]
    X = encoded_df[feature_columns]
    y = encoded_df[LABEL_COLUMN].astype(int)

    X_train = X
    y_train = y
    test_size = _select_test_size(y)
    if test_size is not None:
        try:
            X_train, _, y_train, _ = train_test_split(
                X,
                y,
                test_size=test_size,
                random_state=42,
                stratify=y,
            )
        except ValueError:
            try:
                X_train, _, y_train, _ = train_test_split(
                    X,
                    y,
                    test_size=test_size,
                    random_state=42,
                    stratify=None,
                )
            except ValueError:
                X_train = X
                y_train = y

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    predictions = model.predict(X)
    proba = model.predict_proba(X)
    if proba.ndim == 2 and proba.shape[1] > 1:
        class_to_index = {int(label): index for index, label in enumerate(model.classes_)}
        positive_index = class_to_index.get(1)
        probabilities = (
            proba[:, positive_index].astype(float)
            if positive_index is not None
            else predictions.astype(float)
        )
    else:
        probabilities = predictions.astype(float)
    # Baseline fairness should reflect observed hiring decisions in the uploaded dataset.
    observed_decisions = y.to_numpy()
    metrics = compute_fairness_metrics(X, observed_decisions, observed_decisions)

    majority_values: dict[str, Any] = {}
    for attribute in COUNTERFACTUAL_PROTECTED_ATTRIBUTES:
        if attribute in normalized_df.columns and not normalized_df[attribute].dropna().empty:
            majority_values[attribute] = normalized_df[attribute].mode().iloc[0]

    return {
        **metrics,
        "bias_detected": not all(metrics["pass_flags"].values()),
        "model": model,
        "label_encoders": encoders,
        "encoded_features": X.reset_index(drop=True),
        "normalized_dataframe": normalized_df.reset_index(drop=True),
        "predictions": predictions.astype(int),
        "probabilities": probabilities.astype(float),
        "feature_names": X.columns.tolist(),
        "majority_values": majority_values,
    }
