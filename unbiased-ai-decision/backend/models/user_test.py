from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class UserTestRecord(BaseModel):
    title: str
    tester_persona: str
    technical_level: str
    session_duration_minutes: int = Field(ge=1)
    test_date: date
    task_given: str
    steps_followed: list[str] = Field(default_factory=list)
    issues_encountered: list[str] = Field(default_factory=list)
    outcome: str
    sdg_relevance: str
    feedback_quote: str
    screenshot_placeholder: str
    improvements_made: list[str] = Field(default_factory=list)
