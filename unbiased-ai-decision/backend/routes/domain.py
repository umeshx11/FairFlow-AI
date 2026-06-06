from __future__ import annotations

from fastapi import APIRouter

from domain_config import list_domain_templates


router = APIRouter()


@router.get("/domain/templates")
def get_domain_templates():
    return {
        "templates": [
            template.model_dump(mode="json") for template in list_domain_templates()
        ]
    }
