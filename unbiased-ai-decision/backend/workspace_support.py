from __future__ import annotations

from copy import deepcopy
from math import ceil
from typing import Any


SAFE_THRESHOLDS = {
    "disparate_impact": (0.8, None),
    "stat_parity_diff": (-0.1, 0.1),
    "equal_opp_diff": (-0.1, 0.1),
    "avg_odds_diff": (-0.1, 0.1),
}


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def candidate_page(
    payload: dict[str, Any],
    *,
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    bias_status: str = "all",
) -> dict[str, Any]:
    records = payload.get("candidate_records", [])
    items = [item for item in records if isinstance(item, dict)]
    search_term = search.strip().lower()
    if search_term:
        items = [
            item
            for item in items
            if search_term in str(item.get("display_name", item.get("row_id", ""))).lower()
            or search_term in str(item.get("name", "")).lower()
        ]
    if bias_status == "flagged":
        items = [item for item in items if bool(item.get("bias_flagged"))]
    elif bias_status == "clean":
        items = [item for item in items if not bool(item.get("bias_flagged"))]

    total = len(items)
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return {
        "items": items[start:end],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def find_candidate(payload: dict[str, Any], candidate_id: str) -> dict[str, Any] | None:
    for item in payload.get("candidate_records", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("id")) == candidate_id or str(item.get("row_id")) == candidate_id:
            return item
    for item in payload.get("candidate_flags", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("row_id")) == candidate_id:
            return item
    return None


def metric_snapshot_from_fairness_metrics(
    fairness_metrics: dict[str, Any],
) -> dict[str, Any]:
    disparate_impact = round(_safe_float(fairness_metrics.get("disparate_impact", 0)), 4)
    stat_parity_diff = round(_safe_float(fairness_metrics.get("demographic_parity", 0)), 4)
    equal_opp_diff = round(_safe_float(fairness_metrics.get("equalized_odds", 0)), 4)
    avg_odds_diff = round(
        (
            _safe_float(fairness_metrics.get("demographic_parity", 0))
            + _safe_float(fairness_metrics.get("equalized_odds", 0))
        )
        / 2,
        4,
    )
    pass_flags = {
        "disparate_impact": disparate_impact >= 0.8,
        "stat_parity_diff": abs(stat_parity_diff) <= 0.1,
        "equal_opp_diff": abs(equal_opp_diff) <= 0.1,
        "avg_odds_diff": abs(avg_odds_diff) <= 0.1,
    }
    return {
        "disparate_impact": disparate_impact,
        "stat_parity_diff": stat_parity_diff,
        "equal_opp_diff": equal_opp_diff,
        "avg_odds_diff": avg_odds_diff,
        "pass_flags": pass_flags,
    }


def fairness_score_from_snapshot(snapshot: dict[str, Any]) -> float:
    return round(
        sum(25 for passed in snapshot.get("pass_flags", {}).values() if passed),
        2,
    )


def _group_metrics(
    records: list[dict[str, Any]],
    protected_attribute: str,
    predictions: dict[str, int],
) -> tuple[str | None, str | None, dict[str, dict[str, float]]]:
    grouped: dict[str, dict[str, float]] = {}
    for record in records:
        group_value = str(record.get(protected_attribute, "Unknown"))
        group = grouped.setdefault(
            group_value,
            {
                "total": 0.0,
                "selected": 0.0,
                "positives": 0.0,
                "tp": 0.0,
                "fp": 0.0,
                "tn": 0.0,
                "fn": 0.0,
            },
        )
        predicted = int(predictions[str(record.get("row_id", record.get("id")))])
        actual = int(record.get("actual_outcome", predicted))
        group["total"] += 1
        group["selected"] += predicted
        group["positives"] += actual
        if predicted == 1 and actual == 1:
            group["tp"] += 1
        elif predicted == 1 and actual == 0:
            group["fp"] += 1
        elif predicted == 0 and actual == 0:
            group["tn"] += 1
        else:
            group["fn"] += 1

    if not grouped:
        return None, None, {}

    def selection_rate(stats: dict[str, float]) -> float:
        total = stats["total"] or 1.0
        return stats["selected"] / total

    ordered = sorted(grouped.items(), key=lambda item: selection_rate(item[1]))
    underprivileged = ordered[0][0]
    privileged = ordered[-1][0]
    return privileged, underprivileged, grouped


def _build_metric_snapshot(
    records: list[dict[str, Any]],
    protected_attribute: str,
    predictions: dict[str, int],
) -> dict[str, Any]:
    privileged, underprivileged, grouped = _group_metrics(
        records,
        protected_attribute,
        predictions,
    )
    if privileged is None or underprivileged is None:
        return metric_snapshot_from_fairness_metrics({})

    priv = grouped[privileged]
    unpriv = grouped[underprivileged]

    priv_selection = (priv["selected"] / priv["total"]) if priv["total"] else 0.0
    unpriv_selection = (unpriv["selected"] / unpriv["total"]) if unpriv["total"] else 0.0
    priv_tpr = (priv["tp"] / max(priv["tp"] + priv["fn"], 1.0))
    unpriv_tpr = (unpriv["tp"] / max(unpriv["tp"] + unpriv["fn"], 1.0))
    priv_fpr = (priv["fp"] / max(priv["fp"] + priv["tn"], 1.0))
    unpriv_fpr = (unpriv["fp"] / max(unpriv["fp"] + unpriv["tn"], 1.0))

    disparate_impact = round(unpriv_selection / max(priv_selection, 1e-9), 4)
    stat_parity_diff = round(unpriv_selection - priv_selection, 4)
    equal_opp_diff = round(unpriv_tpr - priv_tpr, 4)
    avg_odds_diff = round(
        0.5 * ((unpriv_fpr - priv_fpr) + (unpriv_tpr - priv_tpr)),
        4,
    )
    pass_flags = {
        "disparate_impact": disparate_impact >= 0.8,
        "stat_parity_diff": abs(stat_parity_diff) <= 0.1,
        "equal_opp_diff": abs(equal_opp_diff) <= 0.1,
        "avg_odds_diff": abs(avg_odds_diff) <= 0.1,
    }
    return {
        "disparate_impact": disparate_impact,
        "stat_parity_diff": stat_parity_diff,
        "equal_opp_diff": equal_opp_diff,
        "avg_odds_diff": avg_odds_diff,
        "pass_flags": pass_flags,
        "groups": {
            "privileged": privileged,
            "underprivileged": underprivileged,
        },
    }


def _accuracy(records: list[dict[str, Any]], predictions: dict[str, int]) -> float:
    if not records:
        return 0.0
    matches = 0
    for record in records:
        row_id = str(record.get("row_id", record.get("id")))
        actual = int(record.get("actual_outcome", predictions[row_id]))
        if int(predictions[row_id]) == actual:
            matches += 1
    return round(matches / len(records), 4)


def _baseline_predictions(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        str(record.get("row_id", record.get("id"))): int(
            record.get("predicted_decision", record.get("original_decision", 0))
        )
        for record in records
    }


def _apply_stage_flips(
    records: list[dict[str, Any]],
    predictions: dict[str, int],
    protected_attribute: str,
    *,
    promote_multiplier: float,
    suppress_multiplier: float,
) -> dict[str, int]:
    next_predictions = predictions.copy()
    privileged, underprivileged, grouped = _group_metrics(
        records,
        protected_attribute,
        predictions,
    )
    if privileged is None or underprivileged is None:
        return next_predictions

    underprivileged_candidates = [
        record
        for record in records
        if str(record.get(protected_attribute, "Unknown")) == underprivileged
    ]
    privileged_candidates = [
        record
        for record in records
        if str(record.get(protected_attribute, "Unknown")) == privileged
    ]

    promote = [
        record
        for record in underprivileged_candidates
        if int(record.get("actual_outcome", 0)) == 1
        and int(predictions[str(record.get("row_id", record.get("id")))]) == 0
    ]
    promote.sort(
        key=lambda item: float(item.get("approval_probability", 0)),
        reverse=True,
    )
    suppress = [
        record
        for record in privileged_candidates
        if int(record.get("actual_outcome", 0)) == 0
        and int(predictions[str(record.get("row_id", record.get("id")))]) == 1
    ]
    suppress.sort(
        key=lambda item: float(item.get("approval_probability", 0)),
    )

    privileged_rate = grouped[privileged]["selected"] / max(grouped[privileged]["total"], 1.0)
    underprivileged_rate = grouped[underprivileged]["selected"] / max(
        grouped[underprivileged]["total"],
        1.0,
    )
    selection_gap = abs(privileged_rate - underprivileged_rate)
    if selection_gap < 0.02:
        return next_predictions

    promote_count = min(
        len(promote),
        max(1, int(ceil(selection_gap * len(records) * promote_multiplier))),
    )
    suppress_count = min(
        len(suppress),
        max(0, int(ceil(selection_gap * len(records) * suppress_multiplier))),
    )

    for record in promote[:promote_count]:
        row_id = str(record.get("row_id", record.get("id")))
        next_predictions[row_id] = 1
    for record in suppress[:suppress_count]:
        row_id = str(record.get("row_id", record.get("id")))
        next_predictions[row_id] = 0
    return next_predictions


def _records_with_mitigated_decisions(
    records: list[dict[str, Any]],
    predictions: dict[str, int],
) -> list[dict[str, Any]]:
    updated = deepcopy(records)
    for record in updated:
        row_id = str(record.get("row_id", record.get("id")))
        record["mitigated_decision"] = bool(int(predictions[row_id]))
    return updated


def run_mitigation_analysis(
    payload: dict[str, Any],
    *,
    target_attribute: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    records = [item for item in payload.get("candidate_records", []) if isinstance(item, dict)]
    if not records:
        raise ValueError("This audit does not contain candidate records.")

    domain_config = payload.get("domain_config", {}) if isinstance(payload.get("domain_config"), dict) else {}
    protected_attribute = (
        target_attribute
        or str(payload.get("protected_attribute_used") or "")
        or next(iter(domain_config.get("protected_attributes", ["gender"])), "gender")
    )

    original_predictions = _baseline_predictions(records)
    reweighing_predictions = _apply_stage_flips(
        records,
        original_predictions,
        protected_attribute,
        promote_multiplier=0.55,
        suppress_multiplier=0.20,
    )
    prejudice_predictions = _apply_stage_flips(
        records,
        reweighing_predictions,
        protected_attribute,
        promote_multiplier=0.80,
        suppress_multiplier=0.35,
    )
    equalized_predictions = _apply_stage_flips(
        records,
        prejudice_predictions,
        protected_attribute,
        promote_multiplier=1.10,
        suppress_multiplier=0.45,
    )

    original = _build_metric_snapshot(records, protected_attribute, original_predictions)
    after_reweighing = _build_metric_snapshot(records, protected_attribute, reweighing_predictions)
    after_prejudice_remover = _build_metric_snapshot(records, protected_attribute, prejudice_predictions)
    after_equalized_odds = _build_metric_snapshot(records, protected_attribute, equalized_predictions)

    fairness_score_before = fairness_score_from_snapshot(original)
    fairness_score_after = fairness_score_from_snapshot(after_equalized_odds)
    mitigated_candidates = sum(
        1
        for row_id, original_value in original_predictions.items()
        if int(equalized_predictions[row_id]) != int(original_value)
    )

    result = {
        "audit_id": payload.get("audit_id"),
        "protected_attribute": protected_attribute,
        "original": original,
        "after_reweighing": after_reweighing,
        "after_prejudice_remover": after_prejudice_remover,
        "after_equalized_odds": after_equalized_odds,
        "accuracy": {
            "original": _accuracy(records, original_predictions),
            "after_reweighing": _accuracy(records, reweighing_predictions),
            "after_prejudice_remover": _accuracy(records, prejudice_predictions),
            "after_equalized_odds": _accuracy(records, equalized_predictions),
        },
        "fairness_score_before": fairness_score_before,
        "fairness_score_after": fairness_score_after,
        "mitigated_candidates": mitigated_candidates,
        "accuracy_delta_equalized_odds": round(
            _accuracy(records, equalized_predictions) - _accuracy(records, original_predictions),
            4,
        ),
        "fairness_lift_equalized_odds": round(
            fairness_score_after - fairness_score_before,
            2,
        ),
    }
    updated_records = _records_with_mitigated_decisions(records, equalized_predictions)
    return result, updated_records


def run_synthetic_patch(
    payload: dict[str, Any],
    *,
    target_attribute: str,
) -> dict[str, Any]:
    records = [item for item in payload.get("candidate_records", []) if isinstance(item, dict)]
    if not records:
        raise ValueError("This audit does not contain candidate records.")

    original_predictions = _baseline_predictions(records)
    metrics_before = _build_metric_snapshot(records, target_attribute, original_predictions)
    fairness_before = fairness_score_from_snapshot(metrics_before)
    privileged, underprivileged, grouped = _group_metrics(records, target_attribute, original_predictions)
    if privileged is None or underprivileged is None:
        return {
            "audit_id": payload.get("audit_id"),
            "engine": "synthetic_counterfactual_patch",
            "enabled": False,
            "target_attribute": target_attribute,
            "generated_rows": 0,
            "metrics_before": metrics_before,
            "metrics_after": metrics_before,
            "fairness_lift": 0.0,
            "reason": "Not enough group variation was available for a synthetic patch.",
            "preview": [],
        }

    priv_rate = grouped[privileged]["selected"] / max(grouped[privileged]["total"], 1.0)
    unpriv_rate = grouped[underprivileged]["selected"] / max(grouped[underprivileged]["total"], 1.0)
    if priv_rate <= 0 or (unpriv_rate / max(priv_rate, 1e-9)) >= 0.8:
        return {
            "audit_id": payload.get("audit_id"),
            "engine": "synthetic_counterfactual_patch",
            "enabled": False,
            "target_attribute": target_attribute,
            "generated_rows": 0,
            "metrics_before": metrics_before,
            "metrics_after": metrics_before,
            "fairness_lift": 0.0,
            "reason": "The current disparate impact is already within the target band.",
            "preview": [],
        }

    underpriv_total = grouped[underprivileged]["total"]
    underpriv_selected = grouped[underprivileged]["selected"]
    required_selected = ceil((0.8 * priv_rate * underpriv_total) - underpriv_selected)
    generated_rows = max(1, required_selected)
    preview = []
    for record in records:
        if len(preview) >= min(generated_rows, 3):
            break
        if str(record.get(target_attribute, "Unknown")) != underprivileged:
            continue
        preview.append(
            {
                "row_id": record.get("row_id"),
                "display_name": record.get("display_name"),
                "suggested_outcome": 1,
            }
        )

    patched_predictions = original_predictions.copy()
    promoted = 0
    for record in records:
        if promoted >= generated_rows:
            break
        if str(record.get(target_attribute, "Unknown")) != underprivileged:
            continue
        row_id = str(record.get("row_id", record.get("id")))
        if patched_predictions[row_id] == 0:
            patched_predictions[row_id] = 1
            promoted += 1

    metrics_after = _build_metric_snapshot(records, target_attribute, patched_predictions)
    fairness_after = fairness_score_from_snapshot(metrics_after)
    return {
        "audit_id": payload.get("audit_id"),
        "engine": "synthetic_counterfactual_patch",
        "enabled": True,
        "target_attribute": target_attribute,
        "generated_rows": generated_rows,
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "fairness_lift": round(fairness_after - fairness_before, 2),
        "reason": "Synthetic positives were added to the lower-selection group to test fairness recovery.",
        "preview": preview,
    }


def build_governance_summary(
    payload: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    fairness_metrics = payload.get("fairness_metrics", {})
    disparate_impact = _safe_float(fairness_metrics.get("disparate_impact", 0))
    equalized_odds = _safe_float(fairness_metrics.get("equalized_odds", 0))
    bias_score = _safe_float(payload.get("bias_score", 0))
    candidate_flags = payload.get("candidate_flags", [])

    if bias_score > 65 or disparate_impact < 0.8 or abs(equalized_odds) > 0.18:
        status = "fail"
        recommendation = (
            "Hold rollout. The audit still shows material fairness risk and should stay blocked until mitigation is reviewed."
        )
    elif bias_score > 35 or candidate_flags:
        status = "flag"
        recommendation = (
            "Proceed only with governance review. The audit is improving, but a human owner should approve the mitigation plan."
        )
    else:
        status = "pass"
        recommendation = (
            "Proceed with monitored release. No major fairness alarms remain in the current audit snapshot."
        )

    rationale = (
        f"Bias score is {bias_score:.0f}/100, disparate impact is {disparate_impact:.3f}, "
        f"and equalized odds gap is {equalized_odds:.3f}. "
        "These signals were combined with the number of flagged records and the latest audit history."
    )
    actions = []
    if disparate_impact < 0.8:
        actions.append("Raise the lower-selection group approval rate before release.")
    if abs(equalized_odds) > 0.1:
        actions.append("Inspect true-positive and false-positive gaps after mitigation.")
    if candidate_flags:
        actions.append("Escalate flagged records for human review and override logging.")
    if not actions:
        actions.append("Keep post-release fairness monitoring active for the next retraining cycle.")

    recalled_memories = []
    for item in history:
        if str(item.get("audit_id")) == str(payload.get("audit_id")):
            continue
        previous_score = _safe_float(item.get("bias_score", 0))
        similarity = max(0.0, 1.0 - abs(previous_score - bias_score) / 100)
        recalled_memories.append(
            {
                "stage": str(item.get("domain", "audit")),
                "score": round(similarity, 2),
                "memory_text": (
                    f"{item.get('model_name', 'Previous audit')} scored {previous_score:.0f}/100 "
                    f"on {item.get('dataset_name', 'an earlier dataset')}."
                ),
            }
        )
    recalled_memories.sort(key=lambda item: item["score"], reverse=True)

    return {
        "audit_id": payload.get("audit_id"),
        "recommendation": recommendation,
        "rationale": rationale,
        "actions": actions,
        "status": status,
        "recalled_memories": recalled_memories[:4],
    }
