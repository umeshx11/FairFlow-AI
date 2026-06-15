from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from database import get_db
from audit_pipeline import create_audit_from_dataframe
from domain_config import PRESET_DOMAIN_TEMPLATES
from ml.bias_detector import run_bias_detection
from ml.counterfactual import generate_counterfactual
from models import ResumeSubmission, User
from routers.auth import get_current_user
from utils import calculate_fairness_score, metric_payload, to_serializable

router = APIRouter()

MIN_POOL_SIZE = 10
MIN_RECOMMENDED_RESUME_COUNT = 30
MAX_RESUME_AUDIT_ROWS = 50
EDUCATION_TIER_TO_LEVEL = {
    "Tier 1": "PhD",
    "Tier 2": "Masters",
    "Tier 3": "Bachelors",
    "Unknown": "Unknown",
}

RESUME_AUDIT_COLUMNS = [
    "name",
    "gender",
    "age",
    "ethnicity",
    "years_experience",
    "education_level",
    "hired",
    "skills",
    "previous_companies",
    "caste",
    "religion",
    "disability_status",
    "region",
]


class SingleResumeAuditRequest(BaseModel):
    age: int = Field(default=0, ge=0, le=100)
    gender: str = Field(default="Unknown")
    education_tier: str = Field(default="Unknown")
    years_experience: float = Field(default=0.0, ge=0)
    outcome: int = Field(description="1 for hired/selected, 0 for rejected/not selected")
    domain: str = Field(default="hiring")

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, value: int) -> int:
        if value not in {0, 1}:
            raise ValueError("outcome must be 0 or 1.")
        return value

    @field_validator("gender", "education_tier", "domain", mode="before")
    @classmethod
    def clean_string(cls, value: Any) -> str:
        cleaned = str(value or "").strip()
        return cleaned or "Unknown"


class ResumeAuditCandidate(BaseModel):
    name: str = Field(default="Unknown")
    gender: str = Field(default="Unknown")
    age: int = Field(default=0, ge=0, le=120)
    ethnicity: str = Field(default="Unknown")
    years_experience: float = Field(default=0.0, ge=0)
    education_level: str = Field(default="Unknown")
    hired: int = Field(description="1 for hired/selected, 0 for rejected/not selected")
    skills: str = Field(default="")
    previous_companies: str = Field(default="")
    caste: str = Field(default="Unknown")
    religion: str = Field(default="Unknown")
    disability_status: str = Field(default="Unknown")
    region: str = Field(default="Unknown")

    @field_validator("hired", mode="before")
    @classmethod
    def validate_hired(cls, value: Any) -> int:
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"yes", "y", "true", "1", "hired", "selected"}:
                return 1
            if normalized in {"no", "n", "false", "0", "rejected", "not_hired", "not selected"}:
                return 0
        if value in {0, 1}:
            return int(value)
        raise ValueError("hired must be set to yes/no or 1/0.")

    @field_validator(
        "name",
        "gender",
        "ethnicity",
        "education_level",
        "caste",
        "religion",
        "disability_status",
        "region",
        mode="before",
    )
    @classmethod
    def clean_resume_string(cls, value: Any) -> str:
        cleaned = str(value or "").strip()
        return cleaned if cleaned else "Unknown"

    @field_validator("skills", "previous_companies", mode="before")
    @classmethod
    def clean_optional_string(cls, value: Any) -> str:
        return str(value or "").strip()


class UploadResumesAuditRequest(BaseModel):
    candidates: list[ResumeAuditCandidate] = Field(min_length=1, max_length=MAX_RESUME_AUDIT_ROWS)


def _education_level(education_tier: str) -> str:
    return EDUCATION_TIER_TO_LEVEL.get(education_tier, "Unknown")


def _clean_domain(domain: str) -> str:
    cleaned = str(domain or "hiring").strip().lower()
    return cleaned or "hiring"


def _pool_query(db: Session, user_id, domain: str):
    return (
        db.query(ResumeSubmission)
        .filter(
            ResumeSubmission.user_id == user_id,
            ResumeSubmission.domain == domain,
        )
        .order_by(ResumeSubmission.created_at.asc())
    )


def _submission_to_row(submission: ResumeSubmission, index: int) -> dict[str, Any]:
    return {
        "name": f"Resume {index + 1}",
        "gender": submission.gender or "Unknown",
        "age": int(submission.age or 0),
        "years_experience": float(submission.years_experience or 0.0),
        "education_level": _education_level(submission.education_tier or "Unknown"),
        "hired": int(submission.outcome),
    }


def _pool_dataframe(pool: list[ResumeSubmission]) -> pd.DataFrame:
    return pd.DataFrame([_submission_to_row(submission, index) for index, submission in enumerate(pool)])


def _pool_summary(pool: list[ResumeSubmission]) -> dict[str, Any]:
    gender_counts = Counter((submission.gender or "Unknown") for submission in pool)
    hire_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"hired": 0, "total": 0})
    for submission in pool:
        gender = submission.gender or "Unknown"
        hire_counts[gender]["total"] += 1
        hire_counts[gender]["hired"] += int(submission.outcome)

    hire_rates = {
        gender: round(values["hired"] / values["total"], 4) if values["total"] else 0.0
        for gender, values in hire_counts.items()
    }
    recent = [
        {
            "id": submission.id,
            "created_at": submission.created_at,
            "domain": submission.domain,
            "age": submission.age,
            "gender": submission.gender,
            "education_tier": submission.education_tier,
            "years_experience": submission.years_experience,
            "outcome": submission.outcome,
            "bias_detected": submission.bias_detected,
        }
        for submission in reversed(pool[-5:])
    ]
    return {
        "pool_size": len(pool),
        "min_pool_size": MIN_POOL_SIZE,
        "progress": min(1.0, round(len(pool) / MIN_POOL_SIZE, 4)),
        "gender_distribution": dict(gender_counts),
        "hire_rates": hire_rates,
        "recent_submissions": recent,
    }


def _readiness_issue(pool: list[ResumeSubmission]) -> str | None:
    if len(pool) < MIN_POOL_SIZE:
        return "minimum_pool_size"
    genders = {str(submission.gender or "Unknown").strip().lower() for submission in pool}
    outcomes = {int(submission.outcome) for submission in pool}
    if len(genders) < 2:
        return "gender_diversity"
    if len(outcomes) < 2:
        return "outcome_diversity"
    return None


def _needs_more_data_payload(pool: list[ResumeSubmission], reason: str) -> dict[str, Any]:
    summary = _pool_summary(pool)
    return {
        "bias_detected": False,
        "fairness_score": None,
        "metrics": None,
        "counterfactual": None,
        "summary": "Add more resume outcomes before running group-level fairness metrics.",
        "pool_size": len(pool),
        "needs_more_data": True,
        "needs_more_data_reason": reason,
        "pool": summary,
    }


@router.post("/api/v1/upload-resumes-audit")
def upload_resumes_audit(
    payload: UploadResumesAuditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = [candidate.model_dump() for candidate in payload.candidates]
    dataframe = pd.DataFrame(rows, columns=RESUME_AUDIT_COLUMNS)

    config = PRESET_DOMAIN_TEMPLATES["hiring"].model_copy(deep=True)
    config.protected_attributes = [
        "gender",
        "ethnicity",
        "age",
        "caste",
        "religion",
        "disability_status",
        "region",
    ]
    config.feature_columns = [
        "years_experience",
        "education_level",
        "skills",
        "previous_companies",
    ]

    result = create_audit_from_dataframe(
        dataframe=dataframe,
        parsed_config=config,
        current_user=current_user,
        db=db,
        filename="resume_batch_upload.csv",
        memory_stage="resume_upload",
        auto_detected_domain=False,
        memory_metadata_extra={
            "source": "upload_resumes",
            "low_sample_warning": len(dataframe) < MIN_RECOMMENDED_RESUME_COUNT,
        },
    )
    db.commit()

    response_payload = result["response_payload"]
    audit_id = response_payload["audit"]["id"]
    return {
        "audit_id": audit_id,
        "warning": (
            "Fewer than 30 candidates were uploaded, so the audit may be less accurate."
            if len(dataframe) < MIN_RECOMMENDED_RESUME_COUNT
            else None
        ),
        **response_payload,
    }


@router.post("/api/v1/audit-single-resume")
def audit_single_resume(
    payload: SingleResumeAuditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    domain = _clean_domain(payload.domain)
    submission = ResumeSubmission(
        user_id=current_user.id,
        domain=domain,
        age=payload.age,
        gender=payload.gender,
        education_tier=payload.education_tier,
        years_experience=payload.years_experience,
        outcome=payload.outcome,
    )
    db.add(submission)
    db.flush()

    pool = _pool_query(db, current_user.id, domain).all()
    readiness_issue = _readiness_issue(pool)
    if readiness_issue:
        response = _needs_more_data_payload(pool, readiness_issue)
        submission.bias_result = to_serializable(
            {
                "needs_more_data": True,
                "needs_more_data_reason": readiness_issue,
                "pool_size": len(pool),
            }
        )
        submission.bias_detected = False
        db.commit()
        return response

    dataframe = _pool_dataframe(pool)
    try:
        detection_result = run_bias_detection(
            dataframe,
            label_column="hired",
            protected_attributes=["gender"],
            outcome_positive_value=1,
            feature_columns=["age", "years_experience", "education_level"],
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    metrics = metric_payload(detection_result)
    if "group_selection_rates" in detection_result:
        metrics["group_selection_rates"] = to_serializable(detection_result["group_selection_rates"])

    normalized_df = detection_result["normalized_dataframe"]
    candidate_row = normalized_df.iloc[-1].to_dict()
    counterfactual = generate_counterfactual(
        detection_result["model"],
        candidate_row,
        detection_result["label_encoders"],
        detection_result["majority_values"],
        label_column=detection_result.get("label_column", "hired"),
        protected_attributes=["gender"],
        model_feature_names=detection_result.get("feature_names", []),
    )
    counterfactual = to_serializable(counterfactual)
    fairness_score = calculate_fairness_score(metrics)
    bias_detected = bool(detection_result["bias_detected"] or counterfactual.get("bias_detected"))

    response = {
        "bias_detected": bias_detected,
        "fairness_score": fairness_score,
        "metrics": metrics,
        "counterfactual": counterfactual,
        "summary": (
            f"Resume pool has {len(pool)} submissions. "
            f"Fairness score is {fairness_score:.0f}/100."
        ),
        "pool_size": len(pool),
        "needs_more_data": False,
        "pool": _pool_summary(pool),
    }
    submission.bias_result = to_serializable(
        {
            "fairness_score": fairness_score,
            "metrics": metrics,
            "counterfactual": counterfactual,
            "summary": response["summary"],
            "pool_size": len(pool),
        }
    )
    submission.bias_detected = bias_detected
    db.commit()
    return response


@router.get("/api/v1/resume-pool")
def get_resume_pool(
    domain: str = "hiring",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cleaned_domain = _clean_domain(domain)
    pool = _pool_query(db, current_user.id, cleaned_domain).all()
    return _pool_summary(pool) | {
        "domain": cleaned_domain,
        "needs_more_data": _readiness_issue(pool) is not None,
        "needs_more_data_reason": _readiness_issue(pool),
    }
