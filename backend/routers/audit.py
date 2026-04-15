from io import BytesIO
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from agent.memory_store import store_memory
from database import get_db
from ml.bias_detector import run_bias_detection
from ml.counterfactual import generate_counterfactual
from ml.explainer import explain_candidate
from models import Audit, Candidate, User
from routers.auth import get_current_user
from schemas import AuditResponse, BiasReport
from utils import metric_payload, serialize_audit, serialize_candidate, to_serializable


router = APIRouter()

REQUIRED_COLUMNS = {
    "name",
    "gender",
    "age",
    "ethnicity",
    "years_experience",
    "education_level",
    "hired",
}
OPTIONAL_COLUMNS = {
    "skills": "",
    "previous_companies": "",
}


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    prepared.columns = [column.strip() for column in prepared.columns]
    missing_required = REQUIRED_COLUMNS - set(prepared.columns)
    if missing_required:
        missing = ", ".join(sorted(missing_required))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded CSV is missing required columns: {missing}",
        )

    for column, default_value in OPTIONAL_COLUMNS.items():
        if column not in prepared.columns:
            prepared[column] = default_value

    return prepared


@router.get("/list", response_model=list[AuditResponse])
def list_audits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    audits = (
        db.query(Audit)
        .options(joinedload(Audit.candidates))
        .filter(Audit.user_id == current_user.id)
        .order_by(Audit.created_at.desc())
        .all()
    )
    return [serialize_audit(audit) for audit in audits]


@router.post("/upload", response_model=BiasReport)
async def upload_audit(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filename = file.filename or "uploaded_candidates.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV uploads are supported.")

    try:
        contents = await file.read()
        dataframe = pd.read_csv(BytesIO(contents))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not parse the uploaded CSV.") from exc

    prepared_df = _prepare_dataframe(dataframe)
    detection_result = run_bias_detection(prepared_df)
    metrics = metric_payload(detection_result)

    audit = Audit(
        user_id=current_user.id,
        dataset_name=filename,
        total_candidates=len(prepared_df),
        disparate_impact=metrics["disparate_impact"],
        stat_parity_diff=metrics["stat_parity_diff"],
        equal_opp_diff=metrics["equal_opp_diff"],
        avg_odds_diff=metrics["avg_odds_diff"],
        bias_detected=bool(detection_result["bias_detected"]),
        mitigation_applied=False,
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
        )
        original_decision = bool(int(row["hired"]))
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
                    if key not in {"name", "gender", "ethnicity", "age", "years_experience", "education_level", "skills", "previous_companies", "hired"}
                }
            ),
            skills=str(row.get("skills", "")),
            previous_companies=str(row.get("previous_companies", "")),
        )
        candidates.append(candidate)

    db.add_all(candidates)
    db.flush()

    store_memory(
        db,
        user_id=current_user.id,
        audit=audit,
        stage="upload",
        metadata={
            "bias_detected": bool(detection_result["bias_detected"]),
            "candidate_count": len(candidates),
        },
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
        },
    }
    db.commit()

    return response_payload


@router.get("/{audit_id}", response_model=AuditResponse)
def get_audit(
    audit_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    audit = (
        db.query(Audit)
        .options(joinedload(Audit.candidates))
        .filter(Audit.id == audit_id, Audit.user_id == current_user.id)
        .first()
    )
    if not audit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found.")
    return serialize_audit(audit)
