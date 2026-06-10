from __future__ import annotations
import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import google.generativeai as genai

router = APIRouter()

# Bias word lists
MALE_CODED_WORDS = [
    "rockstar", "ninja", "hacker", "aggressive",
    "dominant", "competitive", "driven", "strong",
    "fearless", "independent", "analytical",
    "decisive", "champion", "warrior", "beast",
    "crushing", "killer", "genius", "wizard",
    "expert", "master", "hero"
]

FEMALE_CODED_WORDS = [
    "nurturing", "collaborative", "supportive",
    "warm", "caring", "empathetic", "sensitive",
    "gentle", "cooperative", "interpersonal",
    "committed", "dependable", "enthusiastic",
    "cheerful", "humble"
]

EXCLUSIONARY_WORDS = [
    "young", "energetic", "fresh graduate",
    "recent graduate", "digital native",
    "fast-paced", "boys", "girls", "guys",
    "manpower", "manmade", "mankind",
    "he or she", "his/her"
]


class JDAnalysisRequest(BaseModel):
    job_description: str
    job_title: str | None = None


@router.post("/jd-audit/analyze")
async def analyze_job_description(
    request: JDAnalysisRequest,
):
    text_lower = (
        request.job_description.lower()
    )
    
    # Find biased words
    found_male = [
        w for w in MALE_CODED_WORDS 
        if w in text_lower
    ]
    found_female = [
        w for w in FEMALE_CODED_WORDS 
        if w in text_lower
    ]
    found_exclusionary = [
        w for w in EXCLUSIONARY_WORDS 
        if w in text_lower
    ]
    
    total_bias_words = (
        len(found_male) + 
        len(found_female) + 
        len(found_exclusionary)
    )
    
    # Calculate bias score (100 = perfect)
    word_count = len(
        request.job_description.split()
    )
    penalty = min(
        total_bias_words * 8, 60
    )
    bias_score = max(100 - penalty, 40)
    
    # Determine bias type
    if len(found_male) > len(found_female):
        bias_type = "male-coded"
        bias_description = (
            "This job description uses "
            "language that statistically "
            "attracts more male applicants."
        )
    elif len(found_female) > len(found_male):
        bias_type = "female-coded"
        bias_description = (
            "This job description uses "
            "language that statistically "
            "attracts more female applicants."
        )
    else:
        bias_type = "neutral"
        bias_description = (
            "Language appears relatively "
            "gender-neutral."
        )
    
    # Get Gemini suggestions
    gemini_suggestions = []
    api_key = os.getenv("GEMINI_API_KEY")
    
    if api_key and total_bias_words > 0:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                "gemini-2.5-flash"
            )
            
            biased_words_str = ", ".join(
                found_male + 
                found_female + 
                found_exclusionary
            )
            
            prompt = f"""You are a job description 
bias consultant.

Job title: {request.job_title or 'Not specified'}

These words in the job description may 
discourage qualified candidates:
{biased_words_str}

For each word, suggest a neutral replacement.
Return a JSON array only. No explanation.
Example format:
[
  {{"original": "rockstar", 
    "replacement": "skilled professional",
    "reason": "attracts male applicants"}},
  {{"original": "nurturing",
    "replacement": "supportive",  
    "reason": "female-coded language"}}
]

Return only valid JSON. Max 5 suggestions."""

            response = model.generate_content(
                prompt
            )
            raw = response.text.strip()
            # Clean markdown if present
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            gemini_suggestions = json.loads(
                raw.strip()
            )
        except Exception as e:
            print(f"Gemini JD error: {e}")
    
    return {
        "bias_score": bias_score,
        "bias_type": bias_type,
        "bias_description": bias_description,
        "male_coded_words": found_male,
        "female_coded_words": found_female,
        "exclusionary_words": found_exclusionary,
        "total_bias_words": total_bias_words,
        "word_count": word_count,
        "gemini_suggestions": gemini_suggestions,
        "sdg_compliant": bias_score >= 80,
    }
