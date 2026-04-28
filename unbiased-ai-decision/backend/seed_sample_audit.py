from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from google.cloud.firestore_v1 import SERVER_TIMESTAMP

from audit_support import attach_certificate_fields
from firebase_config import require_firestore
from local_audit_store import local_audit_exists, local_store_enabled, upsert_local_audit
from sdg_mapping import build_sdg_mapping


def _base_metrics(parity: float, odds: float, fairness: float, calibration: float, impact: float) -> dict[str, float]:
    return {
        "demographic_parity": parity,
        "equalized_odds": odds,
        "individual_fairness": fairness,
        "calibration_error": calibration,
        "disparate_impact": impact,
    }


SAMPLE_AUDITS: dict[str, dict[str, object]] = {
    "sample_hiring_audit": {
        "organization_name": "FairFlow Demo Hiring",
        "model_name": "Resume Screening Model v2",
        "dataset_name": "demo_hiring_candidates.csv",
        "domain": "hiring",
        "domain_config": {
            "domain": "hiring",
            "display_name": "Hiring",
            "outcome_column": "hired",
            "outcome_positive_value": 1,
            "protected_attributes": ["gender", "ethnicity", "age"],
            "feature_columns": ["years_experience", "education_level"],
            "outcome_label": "Hired",
            "subject_label": "Candidate",
            "required_columns": [
                "name",
                "gender",
                "age",
                "ethnicity",
                "years_experience",
                "education_level",
                "hired",
            ],
            "column_map": {
                "record_id": "name",
                "name": "name",
                "gender": "gender",
                "age": "age",
                "ethnicity": "ethnicity",
                "years_experience": "years_experience",
                "education_level": "education_level",
                "outcome": "hired",
            },
        },
        "model_family": "hiring_random_forest",
        "analysis_backend": "vertex_endpoint",
        "bias_score": 74,
        "fairness_metrics": _base_metrics(0.28, 0.22, 0.67, 0.14, 0.72),
        "shap_values": [
            {"feature": "years_experience", "value": 0.3021},
            {"feature": "education_level", "value": 0.2411},
            {"feature": "gender", "value": 0.2094},
            {"feature": "ethnicity", "value": 0.1871},
        ],
        "shap_top3": ["years_experience", "education_level", "gender"],
        "causal_graph_json": {
            "nodes": [
                {"id": "gender"},
                {"id": "ethnicity"},
                {"id": "years_experience"},
                {"id": "education_level"},
                {"id": "hired"},
            ],
            "edges": [
                {"source": "gender", "target": "education_level", "weight": 0.29},
                {"source": "education_level", "target": "hired", "weight": 0.31},
                {"source": "ethnicity", "target": "years_experience", "weight": 0.21},
                {"source": "years_experience", "target": "hired", "weight": 0.35},
            ],
        },
        "causal_pathway": "gender -> education_level -> hired",
        "gemini_explanation": (
            "The hiring audit shows that education level and years of experience are amplifying differences tied to gender. "
            "That pattern can screen out qualified applicants before a recruiter ever reviews them. "
            "The fastest mitigation is to review proxy-heavy features and re-run the shortlist with a human override."
        ),
        "gemini_recommendations": [
            {
                "title": "Re-review candidate H-102",
                "action": "Re-score the candidate after masking education level and gender-correlated signals.",
                "priority": "high",
                "row_id": "H-102",
            }
        ],
        "gemini_legal_risk": "The hiring audit shows elevated US EEOC adverse-impact risk and should be reviewed before production use.",
        "gemini_audit_qa": [
            {
                "question": "Which feature is causing the most bias?",
                "answer": "Education level is acting as the strongest proxy in this hiring sample.",
            }
        ],
        "jurisdiction_risks": [
            {"jurisdiction": "EU", "framework": "AI Act Article 10", "status": "amber", "summary": "Data quality controls need stronger proxy-feature monitoring."},
            {"jurisdiction": "US", "framework": "EEOC four-fifths rule", "status": "red", "summary": "Disparate impact falls below the 0.8 review threshold."},
            {"jurisdiction": "India", "framework": "Algorithmic accountability", "status": "amber", "summary": "Explainability is present but mitigation tracking needs tighter governance."},
        ],
        "candidate_flags": [
            {
                "row_id": "H-102",
                "display_name": "H-102",
                "protected_group": "women",
                "sensitive_attribute": "gender",
                "predicted_decision": 0,
                "actual_outcome": 1,
                "approval_probability": 0.24,
                "primary_drivers": ["education_level", "years_experience"],
                "recommendation_seed": "Escalate this shortlist decision for human review.",
                "shap_values": [
                    {"feature": "education_level", "value": 0.2411},
                    {"feature": "years_experience", "value": 0.3021},
                ],
                "counterfactual": {
                    "row_id": "H-102",
                    "current_probability": 0.24,
                    "suggested_changes": [
                        {"feature": "years_experience", "current_value": 2.0, "suggested_value": 4.0, "direction": "increase"}
                    ],
                },
            }
        ],
        "candidate_records": [
            {
                "id": "H-102",
                "row_id": "H-102",
                "display_name": "H-102",
                "name": "H-102",
                "gender": "Female",
                "ethnicity": "Hispanic",
                "age": 29,
                "years_experience": 2,
                "education_level": "Bachelors",
                "hired": 1,
                "predicted_decision": 0,
                "original_decision": False,
                "actual_outcome": 1,
                "approval_probability": 0.24,
                "bias_flagged": True,
                "sensitive_attribute": "gender",
                "protected_group": "women",
                "primary_drivers": ["education_level", "years_experience"],
                "feature_impacts": [
                    {"feature": "education_level", "value": 0.2411, "current_value": 1.0},
                    {"feature": "years_experience", "value": 0.3021, "current_value": 2.0},
                ],
                "counterfactual_result": {
                    "row_id": "H-102",
                    "current_probability": 0.24,
                    "suggested_changes": [
                        {"feature": "years_experience", "current_value": 2.0, "suggested_value": 4.0, "direction": "increase"}
                    ],
                },
                "feature_payload": {
                    "name": "H-102",
                    "gender": "Female",
                    "ethnicity": "Hispanic",
                    "age": 29,
                    "years_experience": 2,
                    "education_level": "Bachelors",
                    "hired": 1,
                },
            },
            {
                "id": "H-118",
                "row_id": "H-118",
                "display_name": "H-118",
                "name": "H-118",
                "gender": "Male",
                "ethnicity": "White",
                "age": 34,
                "years_experience": 6,
                "education_level": "Masters",
                "hired": 1,
                "predicted_decision": 1,
                "original_decision": True,
                "actual_outcome": 1,
                "approval_probability": 0.81,
                "bias_flagged": False,
                "sensitive_attribute": "gender",
                "protected_group": "men",
                "primary_drivers": ["years_experience", "education_level"],
                "feature_impacts": [
                    {"feature": "years_experience", "value": 0.3021, "current_value": 6.0},
                    {"feature": "education_level", "value": 0.2411, "current_value": 2.0},
                ],
                "counterfactual_result": {},
                "feature_payload": {
                    "name": "H-118",
                    "gender": "Male",
                    "ethnicity": "White",
                    "age": 34,
                    "years_experience": 6,
                    "education_level": "Masters",
                    "hired": 1,
                },
            },
            {
                "id": "H-126",
                "row_id": "H-126",
                "display_name": "H-126",
                "name": "H-126",
                "gender": "Female",
                "ethnicity": "Black",
                "age": 31,
                "years_experience": 3,
                "education_level": "Bachelors",
                "hired": 0,
                "predicted_decision": 0,
                "original_decision": False,
                "actual_outcome": 0,
                "approval_probability": 0.32,
                "bias_flagged": True,
                "sensitive_attribute": "gender",
                "protected_group": "women",
                "primary_drivers": ["education_level", "gender"],
                "feature_impacts": [
                    {"feature": "education_level", "value": 0.2411, "current_value": 1.0},
                    {"feature": "gender", "value": 0.2094, "current_value": 0.0},
                ],
                "counterfactual_result": {
                    "row_id": "H-126",
                    "current_probability": 0.32,
                    "suggested_changes": [
                        {"feature": "years_experience", "current_value": 3.0, "suggested_value": 5.0, "direction": "increase"}
                    ],
                },
                "feature_payload": {
                    "name": "H-126",
                    "gender": "Female",
                    "ethnicity": "Black",
                    "age": 31,
                    "years_experience": 3,
                    "education_level": "Bachelors",
                    "hired": 0,
                },
            },
            {
                "id": "H-131",
                "row_id": "H-131",
                "display_name": "H-131",
                "name": "H-131",
                "gender": "Male",
                "ethnicity": "Asian",
                "age": 27,
                "years_experience": 5,
                "education_level": "Bachelors",
                "hired": 1,
                "predicted_decision": 1,
                "original_decision": True,
                "actual_outcome": 1,
                "approval_probability": 0.72,
                "bias_flagged": False,
                "sensitive_attribute": "gender",
                "protected_group": "men",
                "primary_drivers": ["years_experience", "education_level"],
                "feature_impacts": [
                    {"feature": "years_experience", "value": 0.3021, "current_value": 5.0},
                    {"feature": "education_level", "value": 0.2411, "current_value": 1.0},
                ],
                "counterfactual_result": {},
                "feature_payload": {
                    "name": "H-131",
                    "gender": "Male",
                    "ethnicity": "Asian",
                    "age": 27,
                    "years_experience": 5,
                    "education_level": "Bachelors",
                    "hired": 1,
                },
            },
        ],
        "counterfactuals": [
            {
                "row_id": "H-102",
                "current_probability": 0.24,
                "suggested_changes": [
                    {"feature": "years_experience", "current_value": 2.0, "suggested_value": 4.0, "direction": "increase"}
                ],
            }
        ],
        "status": "completed",
        "stage": "complete",
        "user_id": "guest-demo",
    },
    "sample_lending_audit": {
        "organization_name": "FairFlow Demo Lending",
        "model_name": "Loan Approval Model v3",
        "dataset_name": "demo_loan_applicants.csv",
        "domain": "lending",
        "domain_config": {
            "domain": "lending",
            "display_name": "Lending",
            "outcome_column": "approved",
            "outcome_positive_value": 1,
            "protected_attributes": ["race", "gender"],
            "feature_columns": ["income", "credit_score", "loan_amount"],
            "outcome_label": "Approved",
            "subject_label": "Applicant",
            "required_columns": ["applicant_id", "race", "gender", "income", "credit_score", "loan_amount", "approved"],
            "column_map": {"record_id": "applicant_id", "name": "applicant_id", "outcome": "approved"},
        },
        "model_family": "lending_random_forest",
        "analysis_backend": "vertex_endpoint",
        "bias_score": 59,
        "fairness_metrics": _base_metrics(0.18, 0.12, 0.78, 0.11, 0.81),
        "shap_values": [
            {"feature": "credit_score", "value": 0.331},
            {"feature": "loan_amount", "value": 0.226},
            {"feature": "race", "value": 0.179},
            {"feature": "gender", "value": 0.144},
        ],
        "shap_top3": ["credit_score", "loan_amount", "race"],
        "causal_graph_json": {
            "nodes": [
                {"id": "race"},
                {"id": "gender"},
                {"id": "credit_score"},
                {"id": "loan_amount"},
                {"id": "approved"},
            ],
            "edges": [
                {"source": "race", "target": "credit_score", "weight": 0.24},
                {"source": "credit_score", "target": "approved", "weight": 0.36},
                {"source": "gender", "target": "loan_amount", "weight": 0.12},
                {"source": "loan_amount", "target": "approved", "weight": 0.26},
            ],
        },
        "causal_pathway": "race -> credit_score -> approved",
        "gemini_explanation": (
            "The lending audit shows that credit score is carrying risk patterns correlated with race. "
            "That can quietly reduce access to credit for applicants who look similar on paper. "
            "The most important mitigation is to audit proxy-heavy variables before an approval decision is finalized."
        ),
        "gemini_recommendations": [],
        "gemini_legal_risk": "The lending audit is close to the four-fifths threshold and should be monitored after each retraining cycle.",
        "gemini_audit_qa": [],
        "jurisdiction_risks": [
            {"jurisdiction": "EU", "framework": "AI Act Article 10", "status": "amber", "summary": "Training data lineage should be documented for credit decisions."},
            {"jurisdiction": "US", "framework": "EEOC four-fifths rule", "status": "green", "summary": "Disparate impact remains above 0.8 in this sample."},
            {"jurisdiction": "India", "framework": "Algorithmic accountability", "status": "amber", "summary": "Model explanations exist but governance evidence should be strengthened."},
        ],
        "candidate_flags": [],
        "counterfactuals": [],
        "status": "completed",
        "stage": "complete",
        "user_id": "guest-demo",
    },
    "sample_medical_audit": {
        "organization_name": "FairFlow Demo Care",
        "model_name": "Triage Prioritization Model v1",
        "dataset_name": "demo_triage_patients.csv",
        "domain": "medical",
        "domain_config": {
            "domain": "medical",
            "display_name": "Medical",
            "outcome_column": "treated",
            "outcome_positive_value": 1,
            "protected_attributes": ["gender", "race"],
            "feature_columns": ["symptom_severity", "insurance_type", "age"],
            "outcome_label": "Treated",
            "subject_label": "Patient",
            "required_columns": ["patient_id", "gender", "race", "age", "insurance_type", "symptom_severity", "treated"],
            "column_map": {"record_id": "patient_id", "name": "patient_id", "outcome": "treated"},
        },
        "model_family": "medical_random_forest",
        "analysis_backend": "vertex_endpoint",
        "bias_score": 41,
        "fairness_metrics": _base_metrics(0.09, 0.07, 0.85, 0.08, 0.93),
        "shap_values": [
            {"feature": "symptom_severity", "value": 0.351},
            {"feature": "insurance_type", "value": 0.149},
            {"feature": "age", "value": 0.127},
            {"feature": "race", "value": 0.098},
        ],
        "shap_top3": ["symptom_severity", "insurance_type", "age"],
        "causal_graph_json": {
            "nodes": [
                {"id": "gender"},
                {"id": "race"},
                {"id": "symptom_severity"},
                {"id": "insurance_type"},
                {"id": "treated"},
            ],
            "edges": [
                {"source": "race", "target": "insurance_type", "weight": 0.15},
                {"source": "insurance_type", "target": "treated", "weight": 0.13},
                {"source": "symptom_severity", "target": "treated", "weight": 0.39},
            ],
        },
        "causal_pathway": "race -> insurance_type -> treated",
        "gemini_explanation": (
            "The triage audit shows a lower level of disparity than the other sample domains, but insurance type still deserves review. "
            "That matters because proxy-heavy triage rules can slow treatment for patients who are already underserved. "
            "The best next step is to keep the model live only with periodic fairness checks and clinician override logging."
        ),
        "gemini_recommendations": [],
        "gemini_legal_risk": "The medical triage sample is lower risk, but clinicians should keep override decisions documented.",
        "gemini_audit_qa": [],
        "jurisdiction_risks": [
            {"jurisdiction": "EU", "framework": "AI Act Article 10", "status": "green", "summary": "Data quality and explainability are within a healthier range for this sample."},
            {"jurisdiction": "US", "framework": "EEOC four-fifths rule", "status": "green", "summary": "Disparate impact remains above 0.8."},
            {"jurisdiction": "India", "framework": "Algorithmic accountability", "status": "green", "summary": "Oversight controls appear proportionate for the demo scenario."},
        ],
        "candidate_flags": [],
        "counterfactuals": [],
        "status": "completed",
        "stage": "complete",
        "user_id": "guest-demo",
    },
}


def _hydrate_payload(document_id: str, payload: dict[str, object]) -> dict[str, object]:
    fairness_metrics = deepcopy(payload["fairness_metrics"])
    shaped = {
        **deepcopy(payload),
        "audit_id": document_id,
        "demographic_parity": fairness_metrics["demographic_parity"],
        "equalized_odds": fairness_metrics["equalized_odds"],
        "individual_fairness": fairness_metrics["individual_fairness"],
        "calibration_error": fairness_metrics["calibration_error"],
        "sdg_mapping": build_sdg_mapping(fairness_metrics),
        "created_at": datetime.now(timezone.utc)
        if local_store_enabled()
        else SERVER_TIMESTAMP,
    }
    return attach_certificate_fields(shaped)


def ensure_sample_audits() -> None:
    if local_store_enabled():
        for document_id, payload in SAMPLE_AUDITS.items():
            if local_audit_exists(document_id):
                continue
            upsert_local_audit(
                document_id,
                _hydrate_payload(document_id, payload),
                merge=False,
            )
        return

    firestore_client = require_firestore()
    for document_id, payload in SAMPLE_AUDITS.items():
        document = firestore_client.collection("audits").document(document_id)
        if document.get().exists:
            continue
        document.set(_hydrate_payload(document_id, payload))


if __name__ == "__main__":
    ensure_sample_audits()
    print("Seeded Firestore guest demo audits.")
