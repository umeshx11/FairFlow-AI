from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status, Depends
from fastapi.responses import FileResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from database import get_db

from demo_workspace import DEMO_WORKSPACE_DATASETS, get_demo_dataset_by_reference_name

limiter = Limiter(key_func=get_remote_address)


router = APIRouter()


@router.get("/datasets")
def list_demo_datasets():
    return {
        "datasets": [
            {
                "domain": dataset["domain"],
                "display_name": dataset["display_name"],
                "reference_dataset_name": dataset["reference_dataset_name"],
                "seed_dataset_name": dataset["seed_dataset_name"],
                "summary": dataset["summary"],
                "download_path": f"/demo/datasets/{dataset['reference_dataset_name']}",
            }
            for dataset in DEMO_WORKSPACE_DATASETS
        ]
    }


@router.get("/datasets/{reference_dataset_name}")
def download_demo_dataset(reference_dataset_name: str):
    dataset = get_demo_dataset_by_reference_name(reference_dataset_name)
    if not dataset or not dataset["file_path"].exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo dataset not found.",
        )

    return FileResponse(
        path=dataset["file_path"],
        media_type="text/csv",
        filename=dataset["reference_dataset_name"],
    )

@router.post("/run")
@limiter.limit("10/hour")  # Max 10 demo runs per IP per hour
async def run_demo_audit(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Runs a pre-seeded audit using 
    sample_hiring_bias_demo.csv.
    No authentication required.
    Returns full audit results immediately.
    """
    import pandas as pd
    from pathlib import Path
    from audit_pipeline import create_audit_from_dataframe
    from domain_config import PRESET_DOMAIN_TEMPLATES
    from models import User

    demo_csv_path = Path(__file__).resolve().parent.parent / "sample_hiring_bias_demo.csv"

    if not demo_csv_path.exists():
        demo_csv_path = (
            Path(__file__).resolve().parent.parent.parent 
            / "sample_hiring_bias_demo.csv"
        )

    if not demo_csv_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Demo dataset not found."
        )

    df = pd.read_csv(demo_csv_path)

    # Get or create demo user
    demo_user = db.query(User).filter(
        User.email == "demo@fairflow.ai"
    ).first()

    if not demo_user:
        from routers.auth import get_password_hash
        demo_user = User(
            email="demo@fairflow.ai",
            hashed_password=get_password_hash(
                "demo-only-no-login"
            ),
            organization="FairFlow Demo",
        )
        db.add(demo_user)
        db.flush()

    config = PRESET_DOMAIN_TEMPLATES["hiring"]

    result = create_audit_from_dataframe(
        dataframe=df,
        parsed_config=config,
        current_user=demo_user,
        db=db,
        filename="sample_hiring_bias_demo.csv",
        memory_stage="upload",
        auto_detected_domain=True,
    )

    db.commit()

    from routers.auth import create_access_token
    from datetime import timedelta
    demo_token = create_access_token(
        {"sub": str(demo_user.id)},
        expires_delta=timedelta(hours=2)
    )

    audit_id = result["response_payload"]["audit"]["id"]

    return {
        **result["response_payload"],
        "demo_mode": True,
        "demo_token": demo_token,
        "demo_user_id": str(demo_user.id),
        "demo_audit_id": audit_id,
        "demo_message": (
            "This is a pre-loaded demo audit using "
            "sample hiring data showing clear gender "
            "bias. Disparate Impact: 0.54 — below "
            "the legal threshold of 0.80."
        ),
    }
