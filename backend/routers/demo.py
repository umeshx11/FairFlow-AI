from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from demo_workspace import DEMO_WORKSPACE_DATASETS, get_demo_dataset_by_reference_name


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
