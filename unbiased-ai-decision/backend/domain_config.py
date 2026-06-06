from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator


SupportedDomain = Literal["hiring", "lending", "medical", "custom"]


def normalize_column_name(value: Any) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


class DomainConfig(BaseModel):
    domain: SupportedDomain
    outcome_column: str
    outcome_positive_value: int | str | bool = 1
    protected_attributes: list[str] = Field(default_factory=list)
    feature_columns: list[str] = Field(default_factory=list)
    display_name: str
    outcome_label: str
    subject_label: str
    required_columns: list[str] = Field(default_factory=list)
    column_map: dict[str, str] = Field(default_factory=dict)

    @field_validator("outcome_column", mode="before")
    @classmethod
    def normalize_outcome_column(cls, value: Any) -> str:
        normalized = normalize_column_name(value)
        if not normalized:
            raise ValueError("outcome_column cannot be empty.")
        return normalized

    @field_validator(
        "protected_attributes",
        "feature_columns",
        "required_columns",
        mode="before",
    )
    @classmethod
    def normalize_list_columns(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            tokens = [token for token in value.split(",") if token.strip()]
            return [normalize_column_name(token) for token in tokens]
        if isinstance(value, list):
            return [
                normalize_column_name(item) for item in value if str(item).strip()
            ]
        raise ValueError("Expected a list of column names.")

    @field_validator("column_map", mode="before")
    @classmethod
    def normalize_column_map(cls, value: Any) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("column_map must be an object.")
        normalized: dict[str, str] = {}
        for key, mapped in value.items():
            normalized_key = normalize_column_name(key)
            normalized_value = normalize_column_name(mapped)
            if normalized_key and normalized_value:
                normalized[normalized_key] = normalized_value
        return normalized

    @model_validator(mode="after")
    def validate_config(self):
        if not self.protected_attributes:
            raise ValueError("At least one protected attribute is required.")
        if self.domain != "custom" and not self.required_columns:
            raise ValueError("required_columns must be provided for preset domains.")
        return self


def _preset_templates() -> dict[str, DomainConfig]:
    return {
        "hiring": DomainConfig(
            domain="hiring",
            outcome_column="hired",
            outcome_positive_value=1,
            protected_attributes=["gender", "ethnicity", "age"],
            feature_columns=["years_experience", "education_level"],
            display_name="Hiring",
            outcome_label="Hired",
            subject_label="Candidate",
            required_columns=[
                "name",
                "gender",
                "age",
                "ethnicity",
                "years_experience",
                "education_level",
                "hired",
            ],
            column_map={
                "record_id": "name",
                "name": "name",
                "gender": "gender",
                "age": "age",
                "ethnicity": "ethnicity",
                "years_experience": "years_experience",
                "education_level": "education_level",
                "outcome": "hired",
            },
        ),
        "lending": DomainConfig(
            domain="lending",
            outcome_column="loan_approved",
            outcome_positive_value=1,
            protected_attributes=["gender", "race", "age"],
            feature_columns=[
                "income",
                "credit_score",
                "loan_amount",
                "employment_years",
                "debt_to_income",
            ],
            display_name="Lending",
            outcome_label="Approved",
            subject_label="Applicant",
            required_columns=[
                "applicant_id",
                "gender",
                "race",
                "age",
                "income",
                "credit_score",
                "loan_amount",
                "employment_years",
                "debt_to_income",
                "loan_approved",
            ],
            column_map={
                "record_id": "applicant_id",
                "name": "applicant_id",
                "gender": "gender",
                "age": "age",
                "ethnicity": "race",
                "years_experience": "employment_years",
                "education_level": "credit_score",
                "outcome": "loan_approved",
            },
        ),
        "medical": DomainConfig(
            domain="medical",
            outcome_column="admitted",
            outcome_positive_value=1,
            protected_attributes=["gender", "race", "age", "insurance_type"],
            feature_columns=[
                "severity_score",
                "wait_time_hours",
                "prior_visits",
                "distance_km",
            ],
            display_name="Medical",
            outcome_label="Admitted",
            subject_label="Patient",
            required_columns=[
                "patient_id",
                "gender",
                "race",
                "age",
                "insurance_type",
                "severity_score",
                "wait_time_hours",
                "prior_visits",
                "distance_km",
                "admitted",
            ],
            column_map={
                "record_id": "patient_id",
                "name": "patient_id",
                "gender": "gender",
                "age": "age",
                "ethnicity": "race",
                "years_experience": "wait_time_hours",
                "education_level": "insurance_type",
                "outcome": "admitted",
            },
        ),
    }


PRESET_DOMAIN_TEMPLATES = _preset_templates()


def list_domain_templates() -> list[DomainConfig]:
    custom = DomainConfig(
        domain="custom",
        outcome_column="outcome",
        outcome_positive_value=1,
        protected_attributes=["gender"],
        feature_columns=[],
        display_name="Custom",
        outcome_label="Outcome",
        subject_label="Record",
        required_columns=[],
        column_map={},
    )
    templates = [
        template.model_copy(deep=True)
        for template in PRESET_DOMAIN_TEMPLATES.values()
    ]
    templates.append(custom)
    return templates


def detect_domain(columns: list[str]) -> DomainConfig | None:
    normalized = {normalize_column_name(column) for column in columns}
    for template in PRESET_DOMAIN_TEMPLATES.values():
        if set(template.required_columns).issubset(normalized):
            return template.model_copy(deep=True)
    return None


def parse_domain_config_payload(
    domain_config_payload: str | None,
    fallback_domain: str | None,
    csv_columns: list[str],
) -> DomainConfig:
    normalized_columns = [normalize_column_name(column) for column in csv_columns]
    payload_data: dict[str, Any] = {}

    if domain_config_payload:
        try:
            payload_data = json.loads(domain_config_payload)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="domain_config must be valid JSON.",
            ) from exc
        if not isinstance(payload_data, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="domain_config must be a JSON object.",
            )

    requested_domain = normalize_column_name(
        payload_data.get("domain") or fallback_domain or ""
    )
    if not requested_domain:
        detected = detect_domain(normalized_columns)
        if detected is not None:
            return detected
        requested_domain = "custom"

    if requested_domain in PRESET_DOMAIN_TEMPLATES:
        base = PRESET_DOMAIN_TEMPLATES[requested_domain].model_copy(deep=True)
        merged = base.model_dump()
        for key in (
            "display_name",
            "outcome_column",
            "outcome_positive_value",
            "protected_attributes",
            "feature_columns",
            "outcome_label",
            "subject_label",
            "required_columns",
            "column_map",
        ):
            if key in payload_data and payload_data[key] is not None:
                merged[key] = payload_data[key]
        return DomainConfig(**merged)

    if requested_domain != "custom":
        supported = ", ".join(["hiring", "lending", "medical", "custom"])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported domain '{requested_domain}'. Supported values: {supported}."
            ),
        )

    custom_payload = {
        "domain": "custom",
        "display_name": payload_data.get("display_name", "Custom"),
        "outcome_column": payload_data.get("outcome_column", "outcome"),
        "outcome_positive_value": payload_data.get("outcome_positive_value", 1),
        "protected_attributes": payload_data.get("protected_attributes", ["gender"]),
        "feature_columns": payload_data.get("feature_columns", []),
        "outcome_label": payload_data.get("outcome_label", "Outcome"),
        "subject_label": payload_data.get("subject_label", "Record"),
        "required_columns": payload_data.get("required_columns", []),
        "column_map": payload_data.get("column_map", {}),
    }
    if not custom_payload["required_columns"]:
        custom_payload["required_columns"] = [
            custom_payload["outcome_column"],
            *custom_payload["protected_attributes"],
            *custom_payload["feature_columns"],
        ]
    return DomainConfig(**custom_payload)


def validate_required_columns(
    config: DomainConfig,
    csv_columns: list[str],
) -> tuple[list[str], list[str]]:
    normalized_columns = [normalize_column_name(column) for column in csv_columns]
    normalized_set = set(normalized_columns)
    missing = [column for column in config.required_columns if column not in normalized_set]
    return missing, normalized_columns
