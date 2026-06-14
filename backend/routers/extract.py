from __future__ import annotations

import asyncio
import base64
import json
import os
from typing import Literal

import google.generativeai as genai
from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
GEMINI_TIMEOUT_SECONDS = 30


class CandidateExtraction(BaseModel):
    name: str = Field(
        default="Unknown",
        description="Candidate name as written on the resume. Use Unknown if unreadable or absent.",
    )
    age: int = Field(
        default=0,
        description=(
            "Age of the candidate in years. "
            "Infer from graduation year if not stated directly. "
            "Use 0 if cannot be determined."
        ),
    )
    gender: Literal["Male", "Female", "Unknown"] = Field(
        default="Unknown",
        description=(
            "Gender of the candidate. "
            "Infer from name or pronouns if not stated. "
            "Use Unknown if cannot be determined."
        ),
    )
    ethnicity: str = Field(
        default="Unknown",
        description="Ethnicity as stated or reasonably available in the resume. Use Unknown if absent.",
    )
    education_level: Literal["Tier 1", "Tier 2", "Tier 3", "Unknown"] = Field(
        default="Unknown",
        description=(
            "Education tier based on institution prestige. "
            "Tier 1: IITs, IIMs, BITS, NIT Top 5, Ivy League, Oxbridge. "
            "Tier 2: Other NITs, IIIT, state govt universities, good private colleges. "
            "Tier 3: Unknown colleges, unaccredited institutions. "
            "Unknown if institution not mentioned."
        ),
    )
    years_experience: float = Field(
        default=0.0,
        description=(
            "Total years of professional work experience as a float. "
            "Calculate from work history dates if listed. "
            "Use 0.0 if no experience or cannot be determined."
        ),
    )
    skills: str = Field(
        default="",
        description="Comma-separated skills found in the resume. Empty string if none are listed.",
    )
    previous_companies: str = Field(
        default="",
        description="Comma-separated previous employers found in the resume. Empty string if none are listed.",
    )
    caste: str = Field(
        default="Unknown",
        description="Caste only if explicitly written on the resume. Never infer. Use Unknown otherwise.",
    )
    religion: str = Field(
        default="Unknown",
        description="Religion only if explicitly written on the resume. Never infer. Use Unknown otherwise.",
    )
    disability_status: str = Field(
        default="Unknown",
        description=(
            "Disability status only if explicitly written on the resume. "
            "Never infer. Use Unknown otherwise."
        ),
    )
    region: str = Field(
        default="Unknown",
        description="Candidate region, location, state, or country as stated or reasonably available.",
    )


@router.post(
    "/api/v1/extract-candidate",
    response_model=CandidateExtraction,
    summary="Extract candidate data from resume",
    description=(
        "Accepts a resume image or PDF and extracts demographic and "
        "professional data using Gemini with structured output."
    ),
)
async def extract_candidate(file: UploadFile) -> CandidateExtraction:
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error": "unsupported_file_type",
                "message": (
                    f"File type '{content_type}' is not supported. "
                    "Upload a JPEG, PNG, or PDF file."
                ),
                "allowed_types": list(ALLOWED_MIME_TYPES),
            },
        )

    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "file_read_error",
                "message": "Could not read the uploaded file.",
            },
        ) from exc

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "empty_file",
                "message": "The uploaded file is empty.",
            },
        )

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": "file_too_large",
                "message": (
                    "File size exceeds the 10MB limit. "
                    f"Uploaded: {len(file_bytes) / 1024 / 1024:.1f}MB."
                ),
            },
        )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "service_unavailable",
                "message": "Gemini API is not configured on this server.",
            },
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-flash-latest")

    prompt = "\n".join(
        [
            "You are a data extraction assistant for an AI fairness auditing platform.",
            "",
            "Extract the following information from this resume.",
            "Return ONLY the structured data, no explanation, no markdown, no commentary.",
            "",
            "Rules:",
            "- name: Candidate name exactly as written when available. Use Unknown if absent.",
            "- age: Integer. Infer from graduation year (assume 22 at bachelor graduation) if not stated.",
            '- gender: Must be exactly "Male", "Female", or "Unknown". Infer from name/pronouns.',
            "- ethnicity: Use only if stated or strongly present in the resume text. Use Unknown if absent.",
            '- education_level: Must be exactly "Tier 1", "Tier 2", "Tier 3", or "Unknown".',
            "  Tier 1 = IITs, IIMs, BITS Pilani, Top NITs, Ivy League, Oxbridge, Stanford, MIT.",
            "  Tier 2 = Other NITs, IIITs, good state universities, reputable private colleges.",
            "  Tier 3 = Unknown or unaccredited institutions.",
            "- years_experience: Float. Sum all work experience durations. Use 0.0 if none found.",
            "- skills: Comma-separated list of skills found in the resume.",
            "- previous_companies: Comma-separated list of previous employers found in the resume.",
            "- region: Region, city/state/country, or location if available. Use Unknown if absent.",
            "- caste: Extract ONLY if explicitly written in the resume. NEVER infer from name, location, language, education, or any other clue. Use Unknown otherwise.",
            "- religion: Extract ONLY if explicitly written in the resume. NEVER infer from name, location, language, education, or any other clue. Use Unknown otherwise.",
            "- disability_status: Extract ONLY if explicitly written in the resume. NEVER infer from wording, gaps, education, or any other clue. Use Unknown otherwise.",
            "",
            "If you cannot read the document clearly, return Unknown/0 for that field.",
            "Do not guess; use Unknown when genuinely uncertain.",
        ]
    )

    image_part = {
        "mime_type": content_type,
        "data": base64.b64encode(file_bytes).decode("utf-8"),
    }

    try:
        response = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: model.generate_content(
                    [prompt, image_part],
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        response_schema=CandidateExtraction,
                        temperature=0.1,
                    ),
                ),
            ),
            timeout=GEMINI_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": "gemini_timeout",
                "message": (
                    "Gemini API did not respond within "
                    f"{GEMINI_TIMEOUT_SECONDS} seconds. Try again."
                ),
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "gemini_api_error",
                "message": f"Gemini API returned an error: {str(exc)}",
            },
        ) from exc

    try:
        raw_text = response.text.strip()
        parsed = json.loads(raw_text)
        extraction = CandidateExtraction(**parsed)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "parse_error",
                "message": (
                    "Gemini returned a response that could not be parsed. "
                    "The document may be unreadable or not a resume."
                ),
                "raw_response": response.text[:500] if response.text else "",
            },
        ) from exc

    return extraction
