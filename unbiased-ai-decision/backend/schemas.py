from __future__ import annotations

from typing import Literal


DomainName = Literal["hiring", "lending", "medical"]


DOMAIN_SCHEMAS: dict[DomainName, dict[str, object]] = {
    "hiring": {
        "target": "hired",
        "protected_attributes": ("gender", "ethnicity"),
        "features": ("gender", "ethnicity", "years_experience", "education_level"),
    },
    "lending": {
        "target": "approved",
        "protected_attributes": ("race", "gender"),
        "features": ("income", "credit_score", "loan_amount", "race", "gender"),
    },
    "medical": {
        "target": "treated",
        "protected_attributes": ("gender", "race"),
        "features": ("age", "gender", "insurance_type", "symptom_severity", "race"),
    },
}


def schema_for_domain(domain: DomainName) -> dict[str, object]:
    return DOMAIN_SCHEMAS[domain]
