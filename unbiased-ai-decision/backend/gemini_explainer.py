from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

try:
    from google import genai
except ImportError:
    genai = None

from runtime_config import has_real_env_value


MODEL_NAME = "gemini-1.5-flash"


def gemini_sdk_available() -> bool:
    return genai is not None


def _client() -> Any | None:
    if not gemini_sdk_available():
        return None
    if not has_real_env_value("GEMINI_API_KEY"):
        return None
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    return genai.Client(api_key=api_key)


def _system_prompt(instruction: str, context: str) -> str:
    return f"SYSTEM INSTRUCTION:\n{instruction}\n\nCONTEXT:\n{context}"


def _parse_json_response(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    try:
        decoded = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            return None
        try:
            decoded = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return decoded if isinstance(decoded, dict) else None


def _generate_json(prompt: str, fallback: dict[str, Any]) -> dict[str, Any]:
    client = _client()
    if client is None:
        return fallback
    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        decoded = _parse_json_response(response.text or "")
        return decoded if decoded is not None else fallback
    except Exception:
        return fallback


def _fallback_explanation(audit_payload: dict[str, Any]) -> str:
    top_feature = ", ".join(audit_payload.get("shap_top3", [])[:1]) or "the strongest proxy feature"
    return (
        f"The audit shows that {top_feature} is driving uneven outcomes across protected groups. "
        "That can turn historical disadvantage into automated decisions that feel objective but are not fair. "
        "The most important next step is to review proxy-heavy features and apply human oversight before release."
    )


def _fallback_recommendations(audit_payload: dict[str, Any]) -> list[dict[str, Any]]:
    flags = audit_payload.get("candidate_flags", [])[:3]
    if not flags:
        return [
            {
                "title": "Retrain with proxy controls",
                "action": "Remove or constrain the strongest proxy-heavy features and compare fairness metrics before deployment.",
                "priority": "high",
                "row_id": None,
            }
        ]
    rows = []
    for flag in flags:
        rows.append(
            {
                "title": f"Review {flag.get('row_id', 'flagged row')}",
                "action": "Re-run this decision with proxy-heavy features masked and record a human override decision.",
                "priority": "high",
                "row_id": flag.get("row_id"),
            }
        )
    return rows


def _fallback_legal_risk(audit_payload: dict[str, Any]) -> str:
    metrics = audit_payload.get("fairness_metrics", {})
    return (
        "This audit should be reviewed for legal exposure because the fairness thresholds are compared directly "
        f"against a disparate impact of {metrics.get('disparate_impact', 0)} and an equalized odds gap of {metrics.get('equalized_odds', 0)}."
    )


def _fallback_jurisdiction_risks(audit_payload: dict[str, Any]) -> list[dict[str, str]]:
    metrics = audit_payload.get("fairness_metrics", {})
    impact = float(metrics.get("disparate_impact", 0) or 0)
    eeoc_status = "green" if impact >= 0.8 else "red"
    return [
        {
            "jurisdiction": "EU",
            "framework": "AI Act Article 10",
            "status": "amber",
            "summary": "Training data quality and proxy monitoring should be documented before deployment.",
        },
        {
            "jurisdiction": "US",
            "framework": "EEOC four-fifths rule",
            "status": eeoc_status,
            "summary": (
                "Disparate impact remains above the four-fifths threshold."
                if eeoc_status == "green"
                else "Disparate impact is below 0.8 and should be treated as a release blocker."
            ),
        },
        {
            "jurisdiction": "India",
            "framework": "Algorithmic accountability",
            "status": "amber",
            "summary": "Explainability exists, but mitigation tracking should be retained for governance review.",
        },
    ]


def _fallback_audit_qa(audit_payload: dict[str, Any]) -> list[dict[str, str]]:
    top_feature = ", ".join(audit_payload.get("shap_top3", [])[:2]) or "the strongest drivers"
    return [
        {
            "question": "Which feature is causing the most bias?",
            "answer": f"The audit points first to {top_feature}.",
        },
        {
            "question": "Is this audit legally compliant?",
            "answer": "Compliance depends on whether the fairness thresholds and mitigation steps are satisfied before release.",
        },
    ]


def generate_gemini_insights(audit_payload: dict[str, Any]) -> dict[str, Any]:
    fallback = {
        "explanation": _fallback_explanation(audit_payload),
        "recommendations": _fallback_recommendations(audit_payload),
        "legal_risk": _fallback_legal_risk(audit_payload),
        "audit_qa": _fallback_audit_qa(audit_payload),
        "jurisdiction_risks": _fallback_jurisdiction_risks(audit_payload),
    }
    prompt = _system_prompt(
        (
            "Return strict JSON with keys explanation, recommendations, legal_risk, audit_qa, jurisdiction_risks. "
            "Use exactly 3 sentences for explanation. "
            "Each recommendation must contain title, action, priority, row_id. "
            "Each audit_qa item must contain question and answer. "
            "Each jurisdiction_risks item must contain jurisdiction, framework, status, summary. "
            "Do not return markdown."
        ),
        json.dumps(
            {
                "domain": audit_payload.get("domain"),
                "metrics": audit_payload.get("fairness_metrics"),
                "candidate_flags": audit_payload.get("candidate_flags", []),
                "counterfactuals": audit_payload.get("counterfactuals", []),
                "sdg_mapping": audit_payload.get("sdg_mapping", {}),
                "shap_top3": audit_payload.get("shap_top3", []),
                "causal_pathway": audit_payload.get("causal_pathway"),
            }
        ),
    )
    decoded = _generate_json(prompt, fallback)
    return {
        "explanation": decoded.get("explanation", fallback["explanation"]),
        "recommendations": decoded.get("recommendations", fallback["recommendations"]),
        "legal_risk": decoded.get("legal_risk", fallback["legal_risk"]),
        "audit_qa": decoded.get("audit_qa", fallback["audit_qa"]),
        "jurisdiction_risks": decoded.get("jurisdiction_risks", fallback["jurisdiction_risks"]),
    }


def explain_flagged_candidate(candidate_payload: dict[str, Any], domain: str) -> str:
    fallback = (
        f"This {domain} decision was flagged because the strongest feature contributions point to "
        f"{', '.join(candidate_payload.get('primary_drivers', [])[:2]) or 'proxy-heavy attributes'}. "
        "That matters because a manager could reject a person for reasons correlated with protected status rather than merit. "
        "The safest next step is to review the case with a human decision-maker before taking action."
    )
    prompt = _system_prompt(
        (
            "You are explaining one flagged fairness case to a non-technical HR manager. "
            "Return exactly 3 sentences in plain English. "
            "Do not use bullets, headings, or legal jargon."
        ),
        json.dumps({"domain": domain, "candidate": candidate_payload}),
    )
    client = _client()
    if client is None:
        return fallback
    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = (response.text or "").strip()
        return text or fallback
    except Exception:
        return fallback


def generate_proxy_explanation(feature_name: str, shap_importance: float, domain: str) -> str:
    fallback = (
        f"{feature_name} carries a SHAP importance of {shap_importance:.3f} and may be acting as a proxy because "
        "it sits close to a protected attribute in the causal graph."
    )
    prompt = _system_prompt(
        (
            "Return exactly one sentence in plain English explaining why a feature may act as a proxy for a protected attribute. "
            "Do not use markdown."
        ),
        json.dumps(
            {
                "feature_name": feature_name,
                "shap_importance": round(shap_importance, 6),
                "domain": domain,
            }
        ),
    )
    client = _client()
    if client is None:
        return fallback
    try:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = (response.text or "").strip()
        return text or fallback
    except Exception:
        return fallback


def _fallback_stream_answer(audit_payload: dict[str, Any], question: str) -> str:
    top_feature = ", ".join(audit_payload.get("shap_top3", [])[:2]) or "the highest-impact features"
    if "legal" in question.lower() or "compliant" in question.lower():
        return _fallback_legal_risk(audit_payload)
    return (
        f"Based on this audit, {top_feature} are the most influential drivers of the current bias pattern. "
        "The fairness metrics and SDG mapping show where the release is closest to a policy threshold. "
        "A reviewer should check mitigation steps before trusting the model in production."
    )


def stream_audit_answer(audit_payload: dict[str, Any], question: str) -> Iterator[str]:
    prompt = _system_prompt(
        (
            "Answer one audit question for a non-technical reviewer. "
            "Return plain text only. Keep the answer concise, accurate, and grounded in the provided audit JSON."
        ),
        json.dumps({"question": question, "audit": audit_payload}),
    )
    client = _client()
    if client is None:
        text = _fallback_stream_answer(audit_payload, question)
        for token in text.split():
            yield token + " "
        return

    try:
        for chunk in client.models.generate_content_stream(model=MODEL_NAME, contents=prompt):
            text = getattr(chunk, "text", "") or ""
            if text:
                yield text
    except Exception:
        text = _fallback_stream_answer(audit_payload, question)
        for token in text.split():
            yield token + " "
