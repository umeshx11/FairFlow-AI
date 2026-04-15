from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np


def laplace_noise(scale: float) -> float:
    scale = max(float(scale), 1e-9)
    return float(np.random.laplace(0.0, scale))


def dp_clip(value: float, lower: float, upper: float) -> float:
    return float(min(upper, max(lower, value)))


def sanitize_metric(value: float, *, epsilon: float, sensitivity: float, lower: float, upper: float) -> float:
    noisy = float(value) + laplace_noise(sensitivity / max(epsilon, 1e-9))
    return dp_clip(noisy, lower, upper)


def sanitize_report_aggregates(
    *,
    metrics: dict[str, float],
    total_candidates: int,
    flagged_candidates: int,
    epsilon: float,
) -> dict[str, Any]:
    epsilon = max(float(epsilon), 0.1)
    n = max(total_candidates, 1)
    sensitivity_rate = 1.0 / n

    dp_metrics = {
        "disparate_impact": round(
            sanitize_metric(
                metrics.get("disparate_impact", 0.0),
                epsilon=epsilon,
                sensitivity=sensitivity_rate,
                lower=0.0,
                upper=2.0,
            ),
            4,
        ),
        "stat_parity_diff": round(
            sanitize_metric(
                metrics.get("stat_parity_diff", 0.0),
                epsilon=epsilon,
                sensitivity=sensitivity_rate,
                lower=-1.0,
                upper=1.0,
            ),
            4,
        ),
        "equal_opp_diff": round(
            sanitize_metric(
                metrics.get("equal_opp_diff", 0.0),
                epsilon=epsilon,
                sensitivity=sensitivity_rate,
                lower=-1.0,
                upper=1.0,
            ),
            4,
        ),
        "avg_odds_diff": round(
            sanitize_metric(
                metrics.get("avg_odds_diff", 0.0),
                epsilon=epsilon,
                sensitivity=sensitivity_rate,
                lower=-1.0,
                upper=1.0,
            ),
            4,
        ),
    }

    noisy_total = int(round(sanitize_metric(total_candidates, epsilon=epsilon, sensitivity=1.0, lower=0, upper=10_000_000)))
    noisy_flagged = int(
        round(sanitize_metric(flagged_candidates, epsilon=epsilon, sensitivity=1.0, lower=0, upper=max(noisy_total, 1)))
    )
    noisy_flagged = min(noisy_flagged, noisy_total)

    return {
        "metrics": dp_metrics,
        "total_candidates": noisy_total,
        "flagged_candidates": noisy_flagged,
        "epsilon": epsilon,
    }


def compute_report_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

