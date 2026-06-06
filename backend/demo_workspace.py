from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

DEMO_WORKSPACE_DATASETS = (
    {
        "domain": "hiring",
        "display_name": "Hiring",
        "seed_dataset_name": "demo_hiring_candidates.csv",
        "reference_dataset_name": "sample_candidates.csv",
        "file_path": BASE_DIR / "sample_candidates.csv",
        "fallback_domain": "hiring",
        "summary": "Candidate shortlisting, selection parity, and fairness risk review",
    },
    {
        "domain": "lending",
        "display_name": "Lending",
        "seed_dataset_name": "demo_loan_applications.csv",
        "reference_dataset_name": "sample_loan_applications.csv",
        "file_path": BASE_DIR / "sample_loan_applications.csv",
        "fallback_domain": "lending",
        "summary": "Approval-rate variance, bias exposure, and decision consistency",
    },
    {
        "domain": "healthcare",
        "display_name": "Healthcare",
        "seed_dataset_name": "demo_medical_admissions.csv",
        "reference_dataset_name": "sample_medical_admissions.csv",
        "file_path": BASE_DIR / "sample_medical_admissions.csv",
        "fallback_domain": "healthcare",
        "summary": "Admission pathway analysis across patient groups and care access",
    },
)


def get_demo_dataset_by_reference_name(reference_dataset_name: str) -> dict | None:
    normalized = reference_dataset_name.strip().lower()
    for dataset in DEMO_WORKSPACE_DATASETS:
        if dataset["reference_dataset_name"].lower() == normalized:
            return dataset
    return None
