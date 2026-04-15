from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from agent.auditor_graph import run_auditor_agent
from agent.memory_store import store_memory
from database import get_db
from models import Audit, User
from routers.auth import get_current_user
from schemas import AuditorDecisionResponse


router = APIRouter()


def _get_audit_for_user(db: Session, audit_id: UUID, user_id) -> Audit:
    audit = (
        db.query(Audit)
        .options(joinedload(Audit.candidates))
        .filter(Audit.id == audit_id, Audit.user_id == user_id)
        .first()
    )
    if not audit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found.")
    return audit


@router.post("/governance/auditor/{audit_id}", response_model=AuditorDecisionResponse)
def run_governance_auditor(
    audit_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    audit = _get_audit_for_user(db, audit_id, current_user.id)
    decision = run_auditor_agent(db=db, audit=audit, user_id=current_user.id)

    store_memory(
        db,
        user_id=current_user.id,
        audit=audit,
        stage="auditor_report",
        metadata={
            "recommendation": decision["recommendation"],
            "actions": ",".join(decision["actions"]),
        },
    )
    db.commit()
    return decision

