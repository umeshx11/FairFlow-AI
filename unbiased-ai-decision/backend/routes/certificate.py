from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from audit_repository import fetch_audit_payload
from models.api_models import FairnessCertificate, SdgMappingResponse


router = APIRouter()


@router.get("/certificate/{audit_id}", response_model=FairnessCertificate)
def get_certificate(audit_id: str):
    try:
        payload = fetch_audit_payload(audit_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found.") from exc

    return FairnessCertificate(
        audit_id=audit_id,
        organization_name=payload.get("organization_name", "FairFlow Demo Organization"),
        audit_date=payload.get("created_at"),
        domain=payload.get("domain", "hiring"),
        fairness_metrics=payload.get("fairness_metrics", {}),
        sdg_mapping=SdgMappingResponse(**payload.get("sdg_mapping", {})),
        certificate_sha256=payload.get("certificate_sha256", ""),
        certified_fair=bool(payload.get("certified_fair")),
        badge_label="CERTIFIED FAIR" if payload.get("certified_fair") else "BIAS DETECTED",
    )
