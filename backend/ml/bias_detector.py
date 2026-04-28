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
    "approved",
    "admitted",
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
    "denied",
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


def _column_lookup(columns: pd.Index | list[str] | tuple[str, ...]) -> dict[str, str]:
    return {_normalize_label_token(column): str(column) for column in columns}


def _resolve_column_name(
    columns: pd.Index | list[str] | tuple[str, ...],
    requested: str | None,
    fallback: str | None = None,
) -> str | None:
    lookup = _column_lookup(columns)
    for candidate in (requested, fallback):
        if not candidate:
            continue
        if candidate in columns:
            return str(candidate)
        resolved = lookup.get(_normalize_label_token(candidate))
        if resolved is not None:
            return resolved
    return None


def _resolve_protected_attributes(
    columns: pd.Index | list[str] | tuple[str, ...],
    *,
    protected_attribute: str | None = None,
    protected_attributes: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    requested = []
    if protected_attribute:
        requested.append(protected_attribute)
    requested.extend(list(protected_attributes or []))
    requested.extend(list(PROTECTED_ATTRIBUTES))

    resolved: list[str] = []
    seen: set[str] = set()
    for candidate in requested:
        actual = _resolve_column_name(columns, candidate)
        if actual is None:
            continue
        normalized = _normalize_label_token(actual)
        if normalized in seen:
            continue
        seen.add(normalized)
        resolved.append(actual)
    return resolved


def normalize_hired_column(
    series: pd.Series,
    *,
    positive_value: Any = 1,
    column_name: str = LABEL_COLUMN,
) -> pd.Series:
    numeric_series = pd.to_numeric(series, errors="coerce")
    positive_numeric = pd.to_numeric(pd.Series([positive_value]), errors="coerce").iloc[0]

    if numeric_series.notna().all():
        unique_values = sorted({float(value) for value in numeric_series.tolist()})
        if len(unique_values) > 2:
            raise ValueError(
                f"Column '{column_name}' must be binary. Supported values include "
                "0/1, yes/no, true/false."
            )
        if pd.notna(positive_numeric) and float(positive_numeric) in unique_values:
            return numeric_series.apply(
                lambda value: 1 if float(value) == float(positive_numeric) else 0
            ).astype(int)
        if set(unique_values).issubset({0.0, 1.0}):
            return numeric_series.astype(int)
        raise ValueError(
            f"Column '{column_name}' must be binary. Supported values include "
            "0/1, yes/no, true/false."
        )

    normalized_tokens = series.map(_normalize_label_token)
    unique_tokens = {token for token in normalized_tokens.tolist() if token}
    positive_token = _normalize_label_token(positive_value)
    custom_binary_mapping = positive_token in unique_tokens and len(unique_tokens) <= 2
    mapped = normalized_tokens.map(
        lambda token: 1
        if token in POSITIVE_LABEL_TOKENS or token == positive_token
        else 0
        if token in NEGATIVE_LABEL_TOKENS or custom_binary_mapping
        else np.nan
    )
    if mapped.isna().any():
        invalid_tokens = sorted(set(normalized_tokens[mapped.isna()].tolist()))[:5]
        raise ValueError(
            f"Column '{column_name}' must be binary. Supported values include "
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


def normalize_dataframe(
    df: pd.DataFrame,
    *,
    label_column: str = LABEL_COLUMN,
    protected_attribute: str | None = None,
    outcome_positive_value: Any = 1,
) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]
    for column in normalized.columns:
        if normalized[column].dtype == object:
            normalized[column] = normalized[column].fillna("Unknown").astype(str).str.strip()
        else:
            normalized[column] = normalized[column].fillna(0)

    resolved_label_column = _resolve_column_name(normalized.columns, label_column, LABEL_COLUMN)
    resolved_protected_attribute = _resolve_column_name(
        normalized.columns,
        protected_attribute,
        _protected_attribute_name(),
    )

    if (
        resolved_protected_attribute is not None
        and _normalize_label_token(resolved_protected_attribute) == "gender"
    ):
        normalized[resolved_protected_attribute] = normalized[resolved_protected_attribute].apply(
            _normalize_gender_value
        )

    if resolved_label_column is not None:
        normalized[resolved_label_column] = normalize_hired_column(
            normalized[resolved_label_column],
            positive_value=outcome_positive_value,
            column_name=resolved_label_column,
        )

    return normalized


def encode_categorical_columns(
    df: pd.DataFrame,
    *,
    label_column: str = LABEL_COLUMN,
    protected_attribute: str | None = None,
) -> tuple[pd.DataFrame, dict[str, LabelEncoder]]:
    encoded = df.copy()
    resolved_label_column = _resolve_column_name(encoded.columns, label_column, LABEL_COLUMN) or label_column
    resolved_protected_attribute = _resolve_column_name(
        encoded.columns,
        protected_attribute,
        _protected_attribute_name(),
    )
    encoders: dict[str, LabelEncoder] = {}
    for column in encoded.columns:
        if column == resolved_label_column:
            continue
        if encoded[column].dtype == object:
            encoder = LabelEncoder()
            encoded[column] = encoder.fit_transform(encoded[column].astype(str))
            encoders[column] = encoder
    if resolved_protected_attribute in encoded.columns:
        encoded.attrs["protected_attribute"] = resolved_protected_attribute
        if resolved_protected_attribute in encoders:
            encoded.attrs["protected_group_labels"] = {
                int(index): str(label)
                for index, label in enumerate(encoders[resolved_protected_attribute].classes_)
            }
    return encoded, encoders


def build_binary_label_dataset(
    encoded_df: pd.DataFrame,
    labels: np.ndarray | None = None,
    *,
    label_column: str = LABEL_COLUMN,
    protected_attribute: str | None = None,
):
    if not AIF360_AVAILABLE:
        return None

    resolved_label_column = _resolve_column_name(encoded_df.columns, label_column, LABEL_COLUMN) or label_column
    resolved_protected_attribute = _resolve_column_name(
        encoded_df.columns,
        protected_attribute,
        _protected_attribute_name(),
    ) or _protected_attribute_name()

    dataset_df = encoded_df.copy()
    if labels is not None:
        dataset_df[resolved_label_column] = labels.astype(int)

    return BinaryLabelDataset(
        favorable_label=1,
        unfavorable_label=0,
        df=dataset_df,
        label_names=[resolved_label_column],
        protected_attribute_names=[resolved_protected_attribute],
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
    *,
    protected_attribute: str | None = None,
) -> dict[str, Any]:
    resolved_protected_attribute = (
        _resolve_column_name(encoded_features.columns, protected_attribute)
        or str(encoded_features.attrs.get("protected_attribute", ""))
        or _protected_attribute_name()
    )
    if resolved_protected_attribute not in encoded_features.columns:
        raise ValueError(
            f"Protected attribute '{resolved_protected_attribute}' not found in encoded features."
        )

    protected = encoded_features[resolved_protected_attribute]
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
        pair_diff = abs(0.5 * ((left_fpr - right_fpr) + (left_tpr - right_tpr)))
        if pair_diff > avg_odds_diff:
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
    *,
    protected_attribute: str | None = None,
) -> dict[str, Any]:
    return _metricframe_payload(
        encoded_features,
        y_true,
        y_pred,
        protected_attribute=protected_attribute,
    )


def compute_fairness_metrics(
    encoded_features: pd.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    protected_attribute: str | None = None,
) -> dict[str, Any]:
    return _metricframe_payload(
        encoded_features,
        y_true,
        y_pred,
        protected_attribute=protected_attribute,
    )


def run_bias_detection(
    df: pd.DataFrame,
    *,
    label_column: str = LABEL_COLUMN,
    protected_attributes: list[str] | tuple[str, ...] | None = None,
    outcome_positive_value: Any = 1,
    feature_columns: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    normalized_df = normalize_dataframe(
        df,
        label_column=label_column,
        protected_attribute=(protected_attributes or [None])[0],
        outcome_positive_value=outcome_positive_value,
    )
    resolved_label_column = _resolve_column_name(
        normalized_df.columns,
        label_column,
        LABEL_COLUMN,
    )
    if resolved_label_column is None:
        raise ValueError(f"Dataset must include a '{label_column}' column.")

    protected_candidates = _resolve_protected_attributes(
        normalized_df.columns,
        protected_attributes=protected_attributes,
    )
    if not protected_candidates:
        requested = list(protected_attributes or PROTECTED_ATTRIBUTES)
        raise ValueError(
            "Dataset must include at least one protected attribute column. "
            f"Expected one of: {requested}"
        )
    protected_attribute = protected_candidates[0]

    encoded_df, encoders = encode_categorical_columns(
        normalized_df,
        label_column=resolved_label_column,
        protected_attribute=protected_attribute,
    )

    available_feature_columns = [
        column
        for column in encoded_df.columns
        if column not in {resolved_label_column, *NON_FEATURE_COLUMNS}
    ]
    resolved_feature_columns: list[str] = []
    if feature_columns:
        for column in feature_columns:
            resolved = _resolve_column_name(available_feature_columns, str(column))
            if resolved is not None and resolved not in resolved_feature_columns:
                resolved_feature_columns.append(resolved)
    if not resolved_feature_columns:
        resolved_feature_columns = available_feature_columns

    model_features = encoded_df[resolved_feature_columns].copy()
    metric_features = model_features.copy()
    if protected_attribute not in metric_features.columns:
        metric_features = pd.concat(
            [metric_features, encoded_df[[protected_attribute]].copy()],
            axis=1,
        )
    metric_features.attrs["protected_attribute"] = protected_attribute
    if protected_attribute in encoders:
        metric_features.attrs["protected_group_labels"] = {
            int(index): str(label)
            for index, label in enumerate(encoders[protected_attribute].classes_)
        }

    y = encoded_df[resolved_label_column].astype(int)

    X_train = model_features
    y_train = y
    test_size = _select_test_size(y)
    if test_size is not None:
        try:
            X_train, _, y_train, _ = train_test_split(
                model_features,
                y,
                test_size=test_size,
                random_state=42,
                stratify=y,
            )
        except ValueError:
            try:
                X_train, _, y_train, _ = train_test_split(
                    model_features,
                    y,
                    test_size=test_size,
                    random_state=42,
                    stratify=None,
                )
            except ValueError:
                X_train = model_features
                y_train = y

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    predictions = model.predict(model_features)
    proba = model.predict_proba(model_features)
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

    observed_decisions = y.to_numpy()
    metrics = compute_fairness_metrics(
        metric_features,
        observed_decisions,
        observed_decisions,
        protected_attribute=protected_attribute,
    )

    majority_values: dict[str, Any] = {}
    for attribute in COUNTERFACTUAL_PROTECTED_ATTRIBUTES:
        if attribute in normalized_df.columns and not normalized_df[attribute].dropna().empty:
            majority_values[attribute] = normalized_df[attribute].mode().iloc[0]
    for feature in resolved_feature_columns:
        if feature in normalized_df.columns and feature not in majority_values:
            non_null_values = normalized_df[feature].dropna()
            if not non_null_values.empty:
                majority_values[feature] = non_null_values.mode().iloc[0]

    return {
        **metrics,
        "bias_detected": not all(metrics["pass_flags"].values()),
        "model": model,
        "label_encoders": encoders,
        "encoded_features": model_features.reset_index(drop=True),
        "normalized_dataframe": normalized_df.reset_index(drop=True),
        "predictions": predictions.astype(int),
        "probabilities": probabilities.astype(float),
        "feature_names": resolved_feature_columns,
        "majority_values": majority_values,
        "label_column": resolved_label_column,
        "protected_attributes": protected_candidates,
        "protected_attribute": protected_attribute,
        "outcome_positive_value": outcome_positive_value,
    }
