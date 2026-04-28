from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from agent.memory_store import store_memory
from domain_config import DomainConfig
from ml.bias_detector import run_bias_detection
from ml.counterfactual import generate_counterfactual
from ml.cultural_audit import run_cultural_bias_scan
from ml.explainer import explain_candidate
from models import Audit, Candidate, User
from utils import metric_payload, serialize_audit, serialize_candidate, to_serializable


OPTIONAL_COLUMNS = {
    "skills": "",
    "previous_companies": "",
    "caste": "Unknown",
    "religion": "Unknown",
    "disability_status": "Unknown",
    "region": "Unknown",
    "dialect": "Unknown",
    "email": "",
    "phone": "",
}

EXCLUDED_CANDIDATE_FEATURE_COLUMNS = {
    "name",
    "gender",
    "ethnicity",
    "age",
    "years_experience",
    "education_level",
    "skills",
    "previous_companies",
    "hired",
}

CANONICAL_DEFAULTS: dict[str, Any] = {
    "name": "Unknown",
    "gender": "Unknown",
    "age": 0,
    "ethnicity": "Unknown",
    "years_experience": 0.0,
    "education_level": "Unknown",
    "hired": 0,
}


def normalize_column_name(column_name: Any) -> str:
    return (
        str(column_name)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def normalized_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    prepared.columns = [normalize_column_name(column) for column in prepared.columns]
    if len(set(prepared.columns)) != len(prepared.columns):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "invalid_schema",
                "message": "Uploaded CSV has duplicate columns after normalization.",
            },
        )
    return prepared


def schema_error_payload(config: DomainConfig, missing_columns: list[str], found_columns: list[str]) -> dict[str, Any]:
    return {
        "error": "invalid_schema",
        "domain": config.domain,
        "missing_columns": missing_columns,
        "found_columns": found_columns,
        "message": (
            f"Your CSV is missing {len(missing_columns)} required columns for the "
            f"{config.display_name} domain."
        ),
    }


def build_canonical_dataframe(df: pd.DataFrame, config: DomainConfig) -> pd.DataFrame:
    prepared = normalized_dataframe(df)
    row_count = len(prepared.index)

    canonical: dict[str, Any] = {}
    for canonical_column in (
        "name",
        "gender",
        "age",
        "ethnicity",
        "years_experience",
        "education_level",
        "hired",
    ):
        source_column = normalize_column_name(config.column_map.get(canonical_column, canonical_column))
        if source_column in prepared.columns:
            canonical[canonical_column] = prepared[source_column].reset_index(drop=True)
        else:
            default_value = CANONICAL_DEFAULTS[canonical_column]
            canonical[canonical_column] = pd.Series([default_value] * row_count)

    canonical_df = pd.DataFrame(canonical)

    for column, default_value in OPTIONAL_COLUMNS.items():
        if column in prepared.columns:
            canonical_df[column] = prepared[column]
        else:
            canonical_df[column] = default_value

    for column in prepared.columns:
        if column in canonical_df.columns:
            continue
        canonical_df[column] = prepared[column]

    return canonical_df


def create_audit_from_dataframe(
    *,
    dataframe: pd.DataFrame,
    parsed_config: DomainConfig,
    current_user: User,
    db: Session,
    filename: str,
    memory_stage: str = "upload",
    auto_detected_domain: bool = False,
    memory_metadata_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_df = build_canonical_dataframe(dataframe, parsed_config)

    try:
        detection_result = run_bias_detection(
            canonical_df,
            label_column=parsed_config.outcome_column if parsed_config.outcome_column in canonical_df.columns else "hired",
            protected_attributes=parsed_config.protected_attributes,
            outcome_positive_value=parsed_config.outcome_positive_value,
            feature_columns=parsed_config.feature_columns,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        cultural_scan = run_cultural_bias_scan(
            canonical_df,
            decision_column=parsed_config.outcome_column if parsed_config.outcome_column in canonical_df.columns else "hired",
            positive_value=parsed_config.outcome_positive_value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    metrics = metric_payload(detection_result)
    parsed_config_payload = parsed_config.model_dump(mode="json")

    audit = Audit(
        user_id=current_user.id,
        dataset_name=filename,
        total_candidates=len(canonical_df),
        disparate_impact=metrics["disparate_impact"],
        stat_parity_diff=metrics["stat_parity_diff"],
        equal_opp_diff=metrics["equal_opp_diff"],
        avg_odds_diff=metrics["avg_odds_diff"],
        bias_detected=bool(detection_result["bias_detected"]),
        mitigation_applied=False,
        domain_config=parsed_config_payload,
    )
    db.add(audit)
    db.flush()

    candidates: list[Candidate] = []
    feature_frame = detection_result["encoded_features"]
    normalized_df = detection_result["normalized_dataframe"]

    for index, row in normalized_df.iterrows():
        explanation = explain_candidate(
            detection_result["model"],
            feature_frame,
            index,
            detection_result["feature_names"],
        )
        counterfactual = generate_counterfactual(
            detection_result["model"],
            row.to_dict(),
            detection_result["label_encoders"],
            detection_result["majority_values"],
            label_column=detection_result.get("label_column", "hired"),
            protected_attributes=parsed_config.protected_attributes,
            model_feature_names=detection_result.get("feature_names", []),
        )
        decision_column = detection_result.get("label_column", "hired")
        original_decision = bool(int(row.get(decision_column, row.get("hired", 0))))
        bias_flagged = bool(counterfactual["bias_detected"] or explanation["proxy_flags"])

        candidate = Candidate(
            audit_id=audit.id,
            name=str(row["name"]),
            gender=str(row["gender"]),
            ethnicity=str(row["ethnicity"]),
            age=int(row["age"]),
            years_experience=float(row["years_experience"]),
            education_level=str(row["education_level"]),
            original_decision=original_decision,
            mitigated_decision=original_decision,
            bias_flagged=bias_flagged,
            shap_values=to_serializable(explanation),
            counterfactual_result=to_serializable(counterfactual),
            feature_payload=to_serializable(
                {
                    key: value
                    for key, value in row.to_dict().items()
                    if key not in EXCLUDED_CANDIDATE_FEATURE_COLUMNS
                }
            ),
            skills=str(row.get("skills", "")),
            previous_companies=str(row.get("previous_companies", "")),
        )
        candidates.append(candidate)

    db.add_all(candidates)
    db.flush()

    memory_metadata = {
        "bias_detected": bool(detection_result["bias_detected"]),
        "candidate_count": len(candidates),
        "high_risk_cultural_dimensions": ",".join(cultural_scan["high_risk_dimensions"]),
        "domain": parsed_config.domain,
        "configured_outcome_column": parsed_config.outcome_column,
        "configured_protected_attrs": ",".join(parsed_config.protected_attributes),
        "auto_detected_domain": auto_detected_domain,
    }
    if memory_metadata_extra:
        memory_metadata.update(memory_metadata_extra)

    store_memory(
        db,
        user_id=current_user.id,
        audit=audit,
        stage=memory_stage,
        metadata=memory_metadata,
    )

    audit.candidates = candidates
    response_payload = {
        "audit": serialize_audit(audit),
        "metrics": metrics,
        "candidates": [serialize_candidate(candidate) for candidate in candidates],
        "summary": {
            "total_candidates": len(candidates),
            "bias_flags": sum(1 for candidate in candidates if candidate.bias_flagged),
            "proxy_flags": sum(
                1
                for candidate in candidates
                if candidate.shap_values and candidate.shap_values.get("proxy_flags")
            ),
            "fairness_score": serialize_audit(audit)["fairness_score"],
            "domain": parsed_config.domain,
            "domain_label": parsed_config.display_name,
            "schema_config": {
                "outcome_column": parsed_config.outcome_column,
                "outcome_positive_value": parsed_config.outcome_positive_value,
                "protected_attributes": parsed_config.protected_attributes,
                "feature_columns": parsed_config.feature_columns,
                "subject_label": parsed_config.subject_label,
                "outcome_label": parsed_config.outcome_label,
            },
            "auto_detected_domain": auto_detected_domain,
            "cultural_scan": cultural_scan,
            "reasoning_log_preview": [
                candidate.shap_values.get("reasoning_log", "")
                for candidate in candidates[:5]
                if candidate.shap_values
            ],
        },
    }

    return {
        "audit": audit,
        "candidates": candidates,
        "response_payload": response_payload,
    }
