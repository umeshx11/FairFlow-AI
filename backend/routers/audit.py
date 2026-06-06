from io import BytesIO
import os
import google.generativeai as genai
from typing import Any
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from agent.memory_store import store_memory
from database import get_db
from domain_config import (
    DomainConfig,
    detect_domain,
    list_domain_templates,
    parse_domain_config_payload,
    validate_required_columns,
)
from ml.bias_detector import run_bias_detection
from ml.counterfactual import generate_counterfactual
from ml.cultural_audit import run_cultural_bias_scan
from ml.explainer import explain_candidate
from ml.multimodal_audit import analyze_multimodal_submission
from models import Audit, Candidate, User
from routers.auth import get_current_user
from schemas import AuditResponse, BiasReport, MultimodalAuditResponse
from utils import metric_payload, serialize_audit, serialize_candidate, to_serializable


router = APIRouter()

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


def _normalize_column_name(column_name: Any) -> str:
    return (
        str(column_name)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def _normalized_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    prepared.columns = [_normalize_column_name(column) for column in prepared.columns]
    if len(set(prepared.columns)) != len(prepared.columns):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "invalid_schema",
                "message": "Uploaded CSV has duplicate columns after normalization.",
            },
        )
    return prepared


def _schema_error_payload(config: DomainConfig, missing_columns: list[str], found_columns: list[str]) -> dict[str, Any]:
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


def _build_canonical_dataframe(df: pd.DataFrame, config: DomainConfig) -> pd.DataFrame:
    prepared = _normalized_dataframe(df)

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
        source_column = _normalize_column_name(config.column_map.get(canonical_column, canonical_column))
        if source_column in prepared.columns:
            canonical[canonical_column] = prepared[source_column]
        else:
            canonical[canonical_column] = CANONICAL_DEFAULTS[canonical_column]

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


@router.get("/templates")
def list_templates_compat():
    templates = list_domain_templates()
    return {
        "templates": {
            template.domain: {
                "label": template.display_name,
                "description": f"{template.display_name} schema preset",
                "required_columns": template.required_columns,
            }
            for template in templates
        }
    }


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
    domain: str = Form(default=""),
    domain_config: str = Form(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filename = file.filename or "uploaded_dataset.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV uploads are supported.")

    try:
        contents = await file.read()
        dataframe = pd.read_csv(BytesIO(contents))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not parse the uploaded CSV.") from exc

    fallback_domain = domain.strip() or None
    parsed_config = parse_domain_config_payload(
        domain_config_payload=domain_config.strip() or None,
        fallback_domain=fallback_domain,
        csv_columns=list(dataframe.columns),
    )

    missing_columns, found_columns = validate_required_columns(parsed_config, list(dataframe.columns))
    if missing_columns:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_schema_error_payload(parsed_config, missing_columns, found_columns),
        )

    auto_detected_domain = False
    if not fallback_domain and not domain_config.strip():
        auto_detected_domain = detect_domain(list(dataframe.columns)) is not None

    canonical_df = _build_canonical_dataframe(dataframe, parsed_config)

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

    store_memory(
        db,
        user_id=current_user.id,
        audit=audit,
        stage="upload",
        metadata={
            "bias_detected": bool(detection_result["bias_detected"]),
            "candidate_count": len(candidates),
            "high_risk_cultural_dimensions": ",".join(cultural_scan["high_risk_dimensions"]),
            "domain": parsed_config.domain,
            "configured_outcome_column": parsed_config.outcome_column,
            "configured_protected_attrs": ",".join(parsed_config.protected_attributes),
            "auto_detected_domain": auto_detected_domain,
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

@router.get("/{audit_id}/gemini-summary")
async def get_gemini_summary(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from models import Audit
    import google.generativeai as genai
    import os
    
    audit = db.query(Audit).filter(
        Audit.id == audit_id,
        Audit.user_id == current_user.id
    ).first()
    
    if not audit:
        raise HTTPException(
            status_code=404, 
            detail="Audit not found"
        )
    
    di = float(audit.disparate_impact or 0)
    spd = float(audit.stat_parity_diff or 0)
    eod = float(audit.equal_opp_diff or 0)
    
    from utils import serialize_audit
    serialized = serialize_audit(audit)
    score = float(serialized.get("fairness_score", 50))
    
    domain_config = audit.domain_config or {}
    domain = str(domain_config.get("domain", "hiring"))
    dataset = str(audit.dataset_name or "dataset")
    
    if di < 0.6:
        risk_level = "high"
    elif di < 0.8:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    
    if gemini_api_key and gemini_api_key != "your-actual-key-here":
        try:
            genai.configure(api_key=gemini_api_key)
            model = genai.GenerativeModel(
                "gemini-1.5-flash"
            )
            
            prompt = f"""You are a fairness compliance 
officer writing a report for a non-technical 
HR manager or hospital administrator.

Audit data:
- Domain: {domain}
- Dataset: {dataset}
- Disparate Impact: {di:.4f} 
  (must be above 0.80 to pass)
- Statistical Parity Difference: {spd:.4f}
  (must be between -0.10 and 0.10 to pass)
- Equal Opportunity Difference: {eod:.4f}
- Overall Fairness Score: {score:.0f} out of 100

Write exactly 3 short paragraphs. 
Use plain English only. No bullet points. 
No technical terms without explanation.
No markdown formatting.

Paragraph 1 (2-3 sentences): What bias was 
found and which group is most affected. 
Use the actual numbers.

Paragraph 2 (2-3 sentences): What the legal 
or business risk is if this is not fixed. 
Mention one specific law: EEOC for hiring in 
the US, EU AI Act for Europe, or India IT Act 
for healthcare or lending in India.

Paragraph 3 (1-2 sentences): The single most 
important action to take this week. Be specific.

End with exactly one sentence starting with 
the words "Bottom line:" on a new line.

Keep total response under 180 words."""

            response = model.generate_content(prompt)
            full_text = response.text.strip()
            
            summary = full_text
            bottom_line = ""
            
            if "Bottom line:" in full_text:
                parts = full_text.split("Bottom line:")
                summary = parts[0].strip()
                bottom_line = "Bottom line:" + parts[1].strip()
            
            return {
                "summary": summary,
                "bottom_line": bottom_line,
                "risk_level": risk_level,
                "disparate_impact": di,
                "fairness_score": score,
                "domain": domain,
                "source": "gemini-1.5-flash"
            }
            
        except Exception as e:
            print(f"Gemini API error: {e}")
            # Fall through to fallback below
    
    # Fallback if API key missing or API fails
    if di < 0.8:
        summary = (
            f"This {domain} dataset shows a Disparate "
            f"Impact of {di:.2f}, which is below the "
            f"legal threshold of 0.80. This means certain "
            f"demographic groups are being selected at "
            f"significantly lower rates than others, "
            f"despite comparable qualifications. "
            f"The overall fairness score is "
            f"{score:.0f}/100, indicating meaningful "
            f"bias risk in the current decision model. "
            f"Under equal opportunity regulations, a "
            f"Disparate Impact below 0.80 constitutes "
            f"evidence of discriminatory selection that "
            f"creates legal and reputational risk for "
            f"your organization. "
            f"This week, apply the reweighing mitigation "
            f"strategy and manually review all rejected "
            f"candidates from affected groups with "
            f"strong qualifications."
        )
        bottom_line = (
            f"Bottom line: Do not deploy this {domain} "
            f"model in production until the Disparate "
            f"Impact rises above 0.80 through verified "
            f"mitigation."
        )
    else:
        summary = (
            f"This {domain} dataset shows a Disparate "
            f"Impact of {di:.2f}, which meets the legal "
            f"threshold of 0.80. No critical demographic "
            f"gaps were detected in the current decision "
            f"patterns. The fairness score of "
            f"{score:.0f}/100 indicates the model is "
            f"operating within acceptable parameters. "
            f"Continue monitoring monthly and re-audit "
            f"after any changes to your pipeline or "
            f"team composition."
        )
        bottom_line = (
            f"Bottom line: Model meets the fairness "
            f"threshold. Schedule the next audit in "
            f"30 days and monitor for drift."
        )
    
    return {
        "summary": summary,
        "bottom_line": bottom_line,
        "risk_level": risk_level,
        "disparate_impact": di,
        "fairness_score": score,
        "domain": domain,
        "source": "fallback"
    }


@router.post("/upload-multimodal", response_model=MultimodalAuditResponse)
async def upload_multimodal_audit(
    file: UploadFile = File(...),
    transcript: str = Form(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_name = file.filename or "multimodal_input"
    if not file_name.lower().endswith((".mp4", ".mov", ".mkv", ".wav", ".mp3", ".m4a")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .mp4/.mov/.mkv and .wav/.mp3/.m4a uploads are supported.",
        )

    payload = await file.read()
    analysis = analyze_multimodal_submission(
        file_name=file_name,
        file_size_bytes=len(payload),
        transcript=transcript,
    )

    pseudo_audit = Audit(
        user_id=current_user.id,
        dataset_name=file_name,
        total_candidates=1,
        disparate_impact=1.0,
        stat_parity_diff=0.0,
        equal_opp_diff=0.0,
        avg_odds_diff=0.0,
        bias_detected=analysis["risk_score"] >= 50,
        mitigation_applied=False,
        domain_config={
            "domain": "custom",
            "display_name": "Multimodal",
            "subject_label": "Interview",
            "outcome_label": "Risk",
            "outcome_column": "risk_score",
            "outcome_positive_value": 1,
            "protected_attributes": ["gender", "ethnicity"],
            "feature_columns": ["transcript", "background"],
            "required_columns": [],
            "column_map": {},
        },
    )
    db.add(pseudo_audit)
    db.flush()

    store_memory(
        db,
        user_id=current_user.id,
        audit=pseudo_audit,
        stage="multimodal_upload",
        metadata={
            "media_type": analysis["media_type"],
            "risk_score": analysis["risk_score"],
            "concerns": ",".join(item["type"] for item in analysis["flagged_concerns"]),
        },
    )
    db.commit()

    return analysis
