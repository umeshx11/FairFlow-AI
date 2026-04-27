from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
from fairlearn.metrics import (
    MetricFrame,
    false_positive_rate,
    selection_rate,
    true_positive_rate,
)
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from utils import compute_pass_flags, metric_payload

try:
    from aif360.datasets import BinaryLabelDataset

    AIF360_AVAILABLE = True
except Exception:
    BinaryLabelDataset = None
    AIF360_AVAILABLE = False


LABEL_COLUMN = "hired"
PROTECTED_ATTRIBUTES = ("gender",)
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

MALE_GENDER_TOKENS = {"m", "male", "man", "cis_male", "cisgender_male", "boy"}
FEMALE_GENDER_TOKENS = {"f", "female", "woman", "cis_female", "cisgender_female", "girl"}
NON_BINARY_GENDER_TOKENS = {
    "nb",
    "n_b",
    "nonbinary",
    "non_binary",
    "non-binary",
    "they_them",
    "they/them",
    "enby",
    "x",
    "other",
    "prefer_not_to_say",
    "prefer-not-to-say",
    "prefer not to say",
    "genderqueer",
    "gender_fluid",
    "gender-fluid",
    "agender",
    "unknown",
    "",
}


def _protected_attribute_name() -> str:
    return PROTECTED_ATTRIBUTES[0]


def _normalize_label_token(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def normalize_hired_column(series: pd.Series) -> pd.Series:
    numeric_series = pd.to_numeric(series, errors="coerce")
    if numeric_series.notna().all():
        if not numeric_series.isin([0, 1]).all():
            invalid_values = sorted(
                set(numeric_series[~numeric_series.isin([0, 1])].tolist())
            )[:5]
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


_normalize_hired_column = normalize_hired_column


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


def _normalize_gender_value(value: Any) -> str:
    token = _normalize_label_token(value)
    if token in MALE_GENDER_TOKENS:
        return "Male"
    if token in FEMALE_GENDER_TOKENS:
        return "Female"
    if token in NON_BINARY_GENDER_TOKENS:
        return "Non-binary"
    return "Non-binary"


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [column.strip() for column in normalized.columns]
    for column in normalized.columns:
        if normalized[column].dtype == object:
            normalized[column] = normalized[column].fillna("Unknown").astype(str).str.strip()
        else:
            normalized[column] = normalized[column].fillna(0)

    protected_attribute = _protected_attribute_name()
    if protected_attribute in normalized.columns:
        normalized[protected_attribute] = normalized[protected_attribute].apply(
            _normalize_gender_value
        )

    if LABEL_COLUMN in normalized.columns:
        normalized[LABEL_COLUMN] = normalize_hired_column(normalized[LABEL_COLUMN])

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
    protected_attribute = _protected_attribute_name()
    if protected_attribute in encoders:
        encoded.attrs["protected_attribute"] = protected_attribute
        encoded.attrs["protected_group_labels"] = {
            int(index): str(label)
            for index, label in enumerate(encoders[protected_attribute].classes_)
        }
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
        protected_attribute_names=[_protected_attribute_name()],
    )


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def _group_label_mapping(encoded_features: pd.DataFrame) -> dict[Any, str]:
    mapping = encoded_features.attrs.get("protected_group_labels", {})
    return mapping if isinstance(mapping, dict) else {}


def _metricframe_payload(
    encoded_features: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, Any]:
    protected_attribute = str(
        encoded_features.attrs.get("protected_attribute", _protected_attribute_name())
    )
    protected = encoded_features[protected_attribute]
    frame = MetricFrame(
        metrics={
            "selection_rate": selection_rate,
            "true_positive_rate": true_positive_rate,
            "false_positive_rate": false_positive_rate,
        },
        y_true=y_true,
        y_pred=y_pred,
        sensitive_features=protected,
    )
    by_group = frame.by_group.fillna(0.0)
    group_mapping = _group_label_mapping(encoded_features)

    def decode_group(group: Any) -> str:
        if group in group_mapping:
            return group_mapping[group]
        try:
            numeric_group = int(group)
        except Exception:
            numeric_group = None
        if numeric_group is not None and numeric_group in group_mapping:
            return group_mapping[numeric_group]
        return str(group)

    selection_by_group = {
        decode_group(group): round(float(value), 4)
        for group, value in by_group["selection_rate"].items()
    }
    selection_values = list(by_group["selection_rate"].astype(float))
    tpr_values = list(by_group["true_positive_rate"].astype(float))
    fpr_values = list(by_group["false_positive_rate"].astype(float))

    best_selection = max(selection_values) if selection_values else 0.0
    worst_selection = min(selection_values) if selection_values else 0.0
    best_tpr = max(tpr_values) if tpr_values else 0.0
    worst_tpr = min(tpr_values) if tpr_values else 0.0

    avg_odds_diff = 0.0
    groups = list(by_group.index)
    for left_group, right_group in combinations(groups, 2):
        left_tpr = float(by_group.loc[left_group, "true_positive_rate"])
        right_tpr = float(by_group.loc[right_group, "true_positive_rate"])
        left_fpr = float(by_group.loc[left_group, "false_positive_rate"])
        right_fpr = float(by_group.loc[right_group, "false_positive_rate"])
        pair_diff = 0.5 * ((left_fpr - right_fpr) + (left_tpr - right_tpr))
        if abs(pair_diff) > abs(avg_odds_diff):
            avg_odds_diff = pair_diff

    raw_metrics = {
        "disparate_impact": _safe_divide(worst_selection, best_selection),
        "stat_parity_diff": worst_selection - best_selection,
        "equal_opp_diff": worst_tpr - best_tpr,
        "avg_odds_diff": avg_odds_diff,
        "group_selection_rates": selection_by_group,
    }
    raw_metrics["pass_flags"] = compute_pass_flags(raw_metrics)
    return metric_payload(raw_metrics) | {
        "group_selection_rates": raw_metrics["group_selection_rates"]
    }


def fallback_metrics(
    encoded_features: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, Any]:
    return _metricframe_payload(encoded_features, y_true, y_pred)


def compute_fairness_metrics(
    encoded_features: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, Any]:
    return _metricframe_payload(encoded_features, y_true, y_pred)


def run_bias_detection(df: pd.DataFrame) -> dict[str, Any]:
    normalized_df = normalize_dataframe(df)
    if LABEL_COLUMN not in normalized_df.columns:
        raise ValueError("Dataset must include a 'hired' column.")
    protected_attribute = _protected_attribute_name()
    if protected_attribute not in normalized_df.columns:
        raise ValueError("Dataset must include a 'gender' column.")

    encoded_df, encoders = encode_categorical_columns(normalized_df)
    feature_columns = [
        column
        for column in encoded_df.columns
        if column not in {LABEL_COLUMN, *NON_FEATURE_COLUMNS}
    ]
    X = encoded_df[feature_columns]
    X.attrs["protected_attribute"] = protected_attribute
    if protected_attribute in encoders:
        X.attrs["protected_group_labels"] = {
            int(index): str(label)
            for index, label in enumerate(encoders[protected_attribute].classes_)
        }
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
