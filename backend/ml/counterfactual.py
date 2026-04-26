from __future__ import annotations

from typing import Any

import pandas as pd


def _encode_candidate(candidate_df: pd.DataFrame, encoders: dict[str, Any]) -> pd.DataFrame:
    encoded = candidate_df.copy()
    for column, encoder in encoders.items():
        if column not in encoded.columns:
            continue
        encoded[column] = encoded[column].astype(str)
        classes = set(getattr(encoder, "classes_", []))
        fallback = next(iter(classes)) if classes else "Unknown"
        encoded[column] = encoded[column].apply(lambda value: value if value in classes else fallback)
        encoded[column] = encoder.transform(encoded[column])
    return encoded


def _positive_probability(model, encoded_frame: pd.DataFrame) -> float:
    if not hasattr(model, "predict_proba"):
        prediction = model.predict(encoded_frame)
        return float(prediction[0]) if len(prediction) else 0.0

    probabilities = model.predict_proba(encoded_frame)
    if getattr(probabilities, "ndim", 0) == 2 and probabilities.shape[1] > 1:
        classes = [int(value) for value in getattr(model, "classes_", [])]
        if 1 in classes:
            positive_index = classes.index(1)
            return float(probabilities[0][positive_index])
        return float(probabilities[0][-1])

    if getattr(probabilities, "ndim", 0) == 2 and probabilities.shape[1] == 1:
        classes = [int(value) for value in getattr(model, "classes_", [])]
        if classes and classes[0] == 1:
            return 1.0
        return 0.0

    prediction = model.predict(encoded_frame)
    return float(prediction[0]) if len(prediction) else 0.0


def generate_counterfactual(model, candidate_row, encoders, majority_values: dict) -> dict:
    if isinstance(candidate_row, pd.Series):
        candidate = candidate_row.to_dict()
    else:
        candidate = dict(candidate_row)

    candidate_features = {
        key: value
        for key, value in candidate.items()
        if key not in {"hired", "original_decision", "name"}
    }
    counterfactual_features = dict(candidate_features)

    changed_attributes: list[str] = []
    for attribute in ("gender", "ethnicity", "caste", "religion", "disability_status", "region", "dialect"):
        if attribute in counterfactual_features and attribute in majority_values:
            if counterfactual_features[attribute] != majority_values[attribute]:
                counterfactual_features[attribute] = majority_values[attribute]
                changed_attributes.append(attribute)

    original_frame = pd.DataFrame([candidate_features])
    counterfactual_frame = pd.DataFrame([counterfactual_features])

    encoded_original = _encode_candidate(original_frame, encoders)
    encoded_counterfactual = _encode_candidate(counterfactual_frame, encoders)

    original_probability = _positive_probability(model, encoded_original)
    counterfactual_probability = _positive_probability(model, encoded_counterfactual)

    original_decision = bool(original_probability >= 0.5)
    counterfactual_decision = bool(counterfactual_probability >= 0.5)
    confidence = round(abs(counterfactual_probability - original_probability), 4)

    return {
        "original_decision": original_decision,
        "counterfactual_decision": counterfactual_decision,
        "bias_detected": counterfactual_decision != original_decision,
        "confidence": confidence,
        "changed_attributes": changed_attributes,
    }
