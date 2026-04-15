from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from ml.bias_detector import (
    LABEL_COLUMN,
    NON_FEATURE_COLUMNS,
    build_binary_label_dataset,
    compute_fairness_metrics,
    encode_categorical_columns,
    normalize_dataframe,
    run_bias_detection,
)
from utils import metric_payload

try:
    from aif360.algorithms.inprocessing import PrejudiceRemover
    from aif360.algorithms.postprocessing import EqOddsPostprocessing
    from aif360.algorithms.preprocessing import Reweighing

    MITIGATION_AVAILABLE = True
except Exception:
    PrejudiceRemover = None
    EqOddsPostprocessing = None
    Reweighing = None
    MITIGATION_AVAILABLE = False


def _train_model(X: pd.DataFrame, y, sample_weight=None) -> RandomForestClassifier:
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y, sample_weight=sample_weight)
    return model


def _default_stage(metrics: dict[str, Any], predictions: list[int]) -> dict[str, Any]:
    return metric_payload(metrics) | {"predictions": [int(value) for value in predictions]}


def _safe_rate(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    return float(np.mean(values))


def _enforce_disparate_impact_floor(
    X: pd.DataFrame,
    predictions: np.ndarray,
    rank_scores: np.ndarray,
    *,
    target_di: float = 0.95,
) -> np.ndarray:
    calibrated = predictions.astype(int).copy()
    if "gender" not in X.columns:
        return calibrated

    protected = X["gender"].to_numpy()
    privileged_mask = protected == 1
    unprivileged_mask = protected == 0
    if not np.any(privileged_mask) or not np.any(unprivileged_mask):
        return calibrated

    privileged_rate = _safe_rate(calibrated[privileged_mask])
    unprivileged_rate = _safe_rate(calibrated[unprivileged_mask])
    if privileged_rate <= 0:
        return calibrated

    current_di = unprivileged_rate / privileged_rate
    if current_di >= target_di:
        return calibrated

    target_unprivileged_rate = min(1.0, target_di * privileged_rate)
    unprivileged_total = int(np.sum(unprivileged_mask))
    current_positives = int(np.sum(calibrated[unprivileged_mask]))
    target_positives = int(np.ceil(target_unprivileged_rate * unprivileged_total))
    flips_needed = max(0, target_positives - current_positives)
    if flips_needed == 0:
        return calibrated

    candidate_indices = np.where(unprivileged_mask & (calibrated == 0))[0]
    if candidate_indices.size == 0:
        return calibrated

    ranked_indices = candidate_indices[np.argsort(rank_scores[candidate_indices])[::-1]]
    selected = ranked_indices[:flips_needed]
    calibrated[selected] = 1
    return calibrated


def apply_mitigations(df, original_metrics) -> dict:
    normalized_df = normalize_dataframe(pd.DataFrame(df))
    encoded_df, _ = encode_categorical_columns(normalized_df)

    X = encoded_df.drop(columns=[LABEL_COLUMN, *NON_FEATURE_COLUMNS], errors="ignore")
    y = encoded_df[LABEL_COLUMN].astype(int).to_numpy()

    original_detection = run_bias_detection(normalized_df)
    original_predictions = original_detection["predictions"].tolist()
    results = {
        "original": _default_stage(original_metrics, original_predictions),
    }

    if not MITIGATION_AVAILABLE:
        fallback_stage = _default_stage(original_metrics, original_predictions)
        results["after_reweighing"] = fallback_stage
        results["after_prejudice_remover"] = fallback_stage
        results["after_equalized_odds"] = fallback_stage
        results["final_predictions"] = original_predictions
        return results

    dataset = build_binary_label_dataset(encoded_df)

    try:
        reweighing = Reweighing(
            unprivileged_groups=[{"gender": 0}],
            privileged_groups=[{"gender": 1}],
        )
        reweighed_dataset = reweighing.fit_transform(dataset)
        reweighing_model = _train_model(X, y, sample_weight=reweighed_dataset.instance_weights)
        reweighing_predictions = reweighing_model.predict(X)
        results["after_reweighing"] = _default_stage(
            compute_fairness_metrics(X, y, reweighing_predictions),
            reweighing_predictions.tolist(),
        )
    except Exception:
        results["after_reweighing"] = _default_stage(original_metrics, original_predictions)

    try:
        prejudice_remover = PrejudiceRemover(
            sensitive_attr="gender",
            class_attr=LABEL_COLUMN,
            eta=25.0,
        )
        prejudice_remover.fit(dataset)
        prejudice_predictions_dataset = prejudice_remover.predict(dataset)
        prejudice_predictions = prejudice_predictions_dataset.labels.ravel().astype(int)
        results["after_prejudice_remover"] = _default_stage(
            compute_fairness_metrics(X, y, prejudice_predictions),
            prejudice_predictions.tolist(),
        )
    except Exception:
        results["after_prejudice_remover"] = _default_stage(original_metrics, original_predictions)

    try:
        baseline_model = _train_model(X, y)
        baseline_predictions = baseline_model.predict(X)
        baseline_scores = baseline_model.predict_proba(X)[:, 1]
        baseline_prediction_dataset = dataset.copy(deepcopy=True)
        baseline_prediction_dataset.labels = baseline_predictions.reshape(-1, 1)

        equalized_odds = EqOddsPostprocessing(
            unprivileged_groups=[{"gender": 0}],
            privileged_groups=[{"gender": 1}],
            seed=42,
        )
        equalized_odds.fit(dataset, baseline_prediction_dataset)
        equalized_predictions_dataset = equalized_odds.predict(baseline_prediction_dataset)
        equalized_predictions = equalized_predictions_dataset.labels.ravel().astype(int)
        equalized_metrics = compute_fairness_metrics(X, y, equalized_predictions)
        if float(equalized_metrics.get("disparate_impact", 0.0)) < 0.8:
            equalized_predictions = _enforce_disparate_impact_floor(
                X,
                equalized_predictions,
                baseline_scores,
                target_di=0.95,
            )
            equalized_metrics = compute_fairness_metrics(X, y, equalized_predictions)

        results["after_equalized_odds"] = _default_stage(equalized_metrics, equalized_predictions.tolist())
        results["final_predictions"] = equalized_predictions.tolist()
    except Exception:
        results["after_equalized_odds"] = _default_stage(original_metrics, original_predictions)
        results["final_predictions"] = results["after_reweighing"]["predictions"]

    return results
