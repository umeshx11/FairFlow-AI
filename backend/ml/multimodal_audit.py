from __future__ import annotations

from typing import Any


def _media_type_from_name(file_name: str) -> str:
    lower = (file_name or "").lower()
    if lower.endswith(".mp4") or lower.endswith(".mov") or lower.endswith(".mkv"):
        return "video"
    if lower.endswith(".wav") or lower.endswith(".mp3") or lower.endswith(".m4a"):
        return "audio"
    return "unknown"


def _estimate_duration_seconds(media_type: str, file_size_bytes: int) -> float:
    size = max(int(file_size_bytes), 1)
    if media_type == "video":
        # Approximate duration assuming ~2 Mbps stream.
        return round((size * 8) / 2_000_000, 1)
    if media_type == "audio":
        # Approximate duration assuming ~192 kbps stream.
        return round((size * 8) / 192_000, 1)
    return 0.0


def analyze_multimodal_submission(
    *,
    file_name: str,
    file_size_bytes: int,
    transcript: str | None = None,
) -> dict[str, Any]:
    media_type = _media_type_from_name(file_name)
    transcript_text = str(transcript or "").strip()
    combined_text = f"{file_name} {transcript_text}".lower()

    concerns: list[dict[str, str]] = []
    if any(token in combined_text for token in ("accent", "dialect", "fluency", "mother tongue")):
        concerns.append(
            {
                "type": "linguistic_fairness",
                "severity": "high",
                "detail": "Interview language cues may proxy for regional or accent bias.",
            }
        )
    if any(token in combined_text for token in ("background", "room", "lighting", "noise", "webcam")):
        concerns.append(
            {
                "type": "environment_proxy_bias",
                "severity": "medium",
                "detail": "Video/audio quality references may proxy for socioeconomic conditions.",
            }
        )
    if any(token in combined_text for token in ("cultural fit", "fitment", "elite", "prestige", "village")):
        concerns.append(
            {
                "type": "socioeconomic_proxy_bias",
                "severity": "high",
                "detail": "Text includes terms commonly correlated with latent socioeconomic proxies.",
            }
        )

    if media_type == "unknown":
        concerns.append(
            {
                "type": "unsupported_media",
                "severity": "high",
                "detail": "Unsupported file type for multimodal fairness pipeline.",
            }
        )

    risk_score = min(100, 18 + len(concerns) * 24)
    reasoning_log = [
        "Observed media metadata and transcript cues for fairness-sensitive language.",
        f"Detected {len(concerns)} concern categories from linguistic, environmental, and socioeconomic signals.",
        "Recommend human review before this interview artifact influences hiring decision calibration.",
    ]
    if not concerns:
        reasoning_log.append("No high-risk lexical proxies detected in current artifact.")

    return {
        "analysis_engine": "gemini-adapter-fallback",
        "media_type": media_type,
        "file_name": file_name,
        "file_size_bytes": int(file_size_bytes),
        "estimated_duration_seconds": _estimate_duration_seconds(media_type, file_size_bytes),
        "risk_score": risk_score,
        "flagged_concerns": concerns,
        "reasoning_log": reasoning_log,
        "recommended_actions": [
            "Run transcript-level fairness review for protected-attribute references.",
            "Ignore background-quality features in ranking decisions.",
            "Require second-reviewer sign-off for high-risk multimodal artifacts.",
        ],
    }
