from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import LinearSVC

try:
    from dowhy import CausalModel

    DOWHY_AVAILABLE = True
except Exception:
    CausalModel = None
    DOWHY_AVAILABLE = False


OUTCOME_COLUMN = "hired"
NON_FEATURE_COLUMNS = {"name"}


def _encode_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, LabelEncoder]]:
    encoded = df.copy()
    encoders: dict[str, LabelEncoder] = {}
    for column in encoded.columns:
        if encoded[column].dtype == object:
            encoder = LabelEncoder()
            encoded[column] = encoder.fit_transform(encoded[column].astype(str))
            encoders[column] = encoder
    return encoded, encoders


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if np.std(a) <= 1e-9 or np.std(b) <= 1e-9:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _estimate_effect(
    encoded_df: pd.DataFrame,
    *,
    feature: str,
    protected: str,
    outcome: str,
) -> float:
    modeling_df = encoded_df[[feature, protected, outcome]].dropna()
    if modeling_df.empty:
        return 0.0

    if DOWHY_AVAILABLE and CausalModel is not None:
        graph = (
            "digraph { "
            f"{protected} -> {feature}; "
            f"{protected} -> {outcome}; "
            f"{feature} -> {outcome}; "
            "}"
        )
        try:
            model = CausalModel(
                data=modeling_df,
                treatment=feature,
                outcome=outcome,
                graph=graph,
            )
            estimand = model.identify_effect(proceed_when_unidentifiable=True)
            estimate = model.estimate_effect(estimand, method_name="backdoor.linear_regression")
            return float(estimate.value)
        except Exception:
            pass

    X = modeling_df[[feature, protected]]
    y = modeling_df[outcome].astype(int)
    if y.nunique() < 2:
        return 0.0
    regression = LogisticRegression(max_iter=400)
    regression.fit(X, y)
    return float(regression.coef_[0][0])


def _token_set(*values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        text = str(value or "").replace("|", " ").replace(",", " ").lower()
        for token in text.split():
            cleaned = token.strip()
            if cleaned:
                tokens.add(cleaned)
    return tokens


def _concept_labels(df: pd.DataFrame) -> dict[str, np.ndarray]:
    skills_series = df.get("skills", pd.Series([""] * len(df)))
    companies_series = df.get("previous_companies", pd.Series([""] * len(df)))
    education_series = df.get("education_level", pd.Series([""] * len(df)))
    experience_series = df.get("years_experience", pd.Series([0.0] * len(df))).astype(float)
    experience_threshold = float(experience_series.median()) if len(df) else 0.0

    leadership_labels = []
    prestige_labels = []
    technical_labels = []
    stability_labels = []

    for skills, companies, education, experience in zip(
        skills_series,
        companies_series,
        education_series,
        experience_series,
    ):
        tokens = _token_set(skills, companies)
        leadership_labels.append(
            1
            if any(token in tokens for token in ("leadership", "manager", "communication", "ownership"))
            else 0
        )
        prestige_labels.append(
            1
            if str(education).strip().lower() in {"master", "phd"} or any(
                token in tokens for token in ("northbridge", "pioneer", "summit", "oakriver")
            )
            else 0
        )
        technical_labels.append(
            1
            if any(token in tokens for token in ("python", "tensorflow", "pytorch", "mlops", "kubernetes"))
            else 0
        )
        stability_labels.append(
            1
            if experience >= experience_threshold and str(companies).count("|") <= 1
            else 0
        )

    return {
        "Leadership": np.array(leadership_labels, dtype=np.int32),
        "EducationPrestige": np.array(prestige_labels, dtype=np.int32),
        "TechnicalDepth": np.array(technical_labels, dtype=np.int32),
        "OperationalStability": np.array(stability_labels, dtype=np.int32),
    }


def _compute_tcav_concepts(
    *,
    encoded_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    feature_columns: list[str],
    outcome: str,
) -> list[dict[str, Any]]:
    X = encoded_df[feature_columns]
    y = encoded_df[outcome].astype(int)
    if y.nunique() < 2:
        return []

    surrogate = LogisticRegression(max_iter=600)
    surrogate.fit(X, y)
    gradient = surrogate.coef_[0]
    concept_labels = _concept_labels(raw_df)

    concepts: list[dict[str, Any]] = []
    for concept_name, labels in concept_labels.items():
        positives = int(np.sum(labels == 1))
        negatives = int(np.sum(labels == 0))
        if positives < 4 or negatives < 4:
            continue

        try:
            cav_model = LinearSVC(max_iter=4000)
            cav_model.fit(X, labels)
            cav = cav_model.coef_[0]
            cav_norm = np.linalg.norm(cav)
            if cav_norm <= 1e-9:
                continue
            cav = cav / cav_norm
        except Exception:
            continue

        sensitivity = float(np.dot(gradient, cav))
        tcav_score = float(1.0 / (1.0 + np.exp(-sensitivity)))
        prevalence = float(positives / len(labels))
        direction = "increases hire propensity" if sensitivity >= 0 else "decreases hire propensity"
        concepts.append(
            {
                "concept": concept_name,
                "tcav_score": round(tcav_score, 4),
                "sensitivity": round(sensitivity, 4),
                "prevalence": round(prevalence, 4),
                "direction": direction,
                "summary": f"{concept_name} concept {direction} based on local CAV projection.",
            }
        )

    concepts.sort(key=lambda item: abs(item["sensitivity"]), reverse=True)
    return concepts


def run_causal_tcav_analysis(df: pd.DataFrame) -> dict[str, Any]:
    if OUTCOME_COLUMN not in df.columns:
        raise ValueError("Dataset must include hired column for causal analysis.")

    protected = "ethnicity" if "ethnicity" in df.columns else "gender"
    if protected not in df.columns:
        raise ValueError("Dataset must include at least one protected attribute (gender or ethnicity).")

    normalized_df = df.copy()
    for column in normalized_df.columns:
        if normalized_df[column].dtype == object:
            normalized_df[column] = normalized_df[column].fillna("Unknown").astype(str).str.strip()
        else:
            normalized_df[column] = normalized_df[column].fillna(0)

    normalized_df[OUTCOME_COLUMN] = normalized_df[OUTCOME_COLUMN].astype(int)
    encoded_df, _ = _encode_dataframe(normalized_df)

    feature_columns = [
        column
        for column in encoded_df.columns
        if column not in {OUTCOME_COLUMN, protected, *NON_FEATURE_COLUMNS}
    ]

    protected_array = encoded_df[protected].to_numpy()
    proxy_findings: list[dict[str, Any]] = []
    dag_edges = [{"source": protected, "target": OUTCOME_COLUMN}]

    for feature in feature_columns:
        feature_array = encoded_df[feature].to_numpy()
        proxy_strength = abs(_safe_corr(feature_array, protected_array))
        effect = _estimate_effect(
            encoded_df,
            feature=feature,
            protected=protected,
            outcome=OUTCOME_COLUMN,
        )
        risk_score = proxy_strength * abs(effect)
        is_proxy = proxy_strength >= 0.25 and abs(effect) >= 0.03
        proxy_findings.append(
            {
                "feature": feature,
                "proxy_strength": round(proxy_strength, 4),
                "treatment_effect": round(effect, 4),
                "risk_score": round(risk_score, 4),
                "is_proxy": bool(is_proxy),
                "explanation": (
                    f"{feature} has proxy-strength {proxy_strength:.3f} with {protected} "
                    f"and causal effect {effect:.3f} on hiring."
                ),
            }
        )
        if is_proxy:
            dag_edges.append({"source": protected, "target": feature})
            dag_edges.append({"source": feature, "target": OUTCOME_COLUMN})

    proxy_findings.sort(key=lambda item: item["risk_score"], reverse=True)
    tcav_concepts = _compute_tcav_concepts(
        encoded_df=encoded_df,
        raw_df=normalized_df,
        feature_columns=feature_columns,
        outcome=OUTCOME_COLUMN,
    )

    return {
        "protected_attribute": protected,
        "dag_edges": dag_edges,
        "proxy_findings": proxy_findings[:10],
        "tcav_concepts": tcav_concepts,
        "engine": "dowhy" if DOWHY_AVAILABLE else "fallback-logistic",
    }

