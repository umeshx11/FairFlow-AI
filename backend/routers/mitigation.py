from io import BytesIO
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session, joinedload

from agent.memory_store import store_memory
from database import get_db
from ml.mitigator import apply_mitigations
from ml.synthetic_patch import generate_synthetic_counterfactual_patch
from models import Audit, AuditCertificate, User
from privacy import compute_report_hash, sanitize_report_aggregates, sanitize_metric
from routers.auth import get_current_user
from schemas import CertificateResponse, MitigationResponse, SyntheticPatchResponse
from utils import calculate_fairness_score, compute_group_hire_rates, metric_payload, rebuild_audit_rows


router = APIRouter()


def _get_audit_for_user(db: Session, audit_id: UUID, user_id) -> Audit:
    audit = (
        db.query(Audit)
        .options(joinedload(Audit.candidates))
        .filter(Audit.id == audit_id, Audit.user_id == user_id)
        .first()
    )
    if not audit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found.")
    return audit


def _stage_accuracy(y_true: list[int], predictions: list[int]) -> float:
    if not y_true or not predictions:
        return 0.0
    total = min(len(y_true), len(predictions))
    matches = sum(1 for index in range(total) if int(y_true[index]) == int(predictions[index]))
    return round(matches / total, 4)


@router.post("/mitigate/{audit_id}", response_model=MitigationResponse)
def mitigate_audit(
    audit_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    audit = _get_audit_for_user(db, audit_id, current_user.id)
    ordered_candidates = list(audit.candidates)
    if not ordered_candidates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This audit does not contain candidates.")

    reconstructed_df = pd.DataFrame(rebuild_audit_rows(ordered_candidates))
    original_metrics = metric_payload(
        {
            "disparate_impact": audit.disparate_impact,
            "stat_parity_diff": audit.stat_parity_diff,
            "equal_opp_diff": audit.equal_opp_diff,
            "avg_odds_diff": audit.avg_odds_diff,
        }
    )
    mitigation_result = apply_mitigations(reconstructed_df, original_metrics)
    y_true = reconstructed_df["hired"].astype(int).tolist()

    final_predictions = mitigation_result.get("final_predictions", [])
    for index, candidate in enumerate(ordered_candidates):
        if index < len(final_predictions):
            candidate.mitigated_decision = bool(final_predictions[index])

    audit.mitigation_applied = True
    original_accuracy = _stage_accuracy(y_true, mitigation_result["original"].get("predictions", []))
    reweighing_accuracy = _stage_accuracy(y_true, mitigation_result["after_reweighing"].get("predictions", []))
    prejudice_accuracy = _stage_accuracy(y_true, mitigation_result["after_prejudice_remover"].get("predictions", []))
    equalized_accuracy = _stage_accuracy(y_true, mitigation_result["after_equalized_odds"].get("predictions", []))
    fairness_before = calculate_fairness_score(mitigation_result["original"])
    fairness_after = calculate_fairness_score(mitigation_result["after_equalized_odds"])

    audit.mitigation_results = {
        "original": mitigation_result["original"],
        "after_reweighing": mitigation_result["after_reweighing"],
        "after_prejudice_remover": mitigation_result["after_prejudice_remover"],
        "after_equalized_odds": mitigation_result["after_equalized_odds"],
        "accuracy": {
            "original": original_accuracy,
            "after_reweighing": reweighing_accuracy,
            "after_prejudice_remover": prejudice_accuracy,
            "after_equalized_odds": equalized_accuracy,
        },
        "accuracy_delta_equalized_odds": round(equalized_accuracy - original_accuracy, 4),
        "fairness_lift_equalized_odds": round(fairness_after - fairness_before, 2),
    }

    store_memory(
        db,
        user_id=current_user.id,
        audit=audit,
        stage="mitigation",
        metadata={
            "method": "equalized_odds",
            "accuracy_delta": round(equalized_accuracy - original_accuracy, 4),
            "fairness_lift": round(fairness_after - fairness_before, 2),
        },
    )
    db.commit()

    fairness_score_before = fairness_before
    fairness_score_after = fairness_after
    mitigated_candidates = sum(
        1
        for candidate in ordered_candidates
        if candidate.mitigated_decision is not None and candidate.mitigated_decision != candidate.original_decision
    )

    return {
        "audit_id": audit.id,
        "original": metric_payload(mitigation_result["original"]),
        "after_reweighing": metric_payload(mitigation_result["after_reweighing"]),
        "after_prejudice_remover": metric_payload(mitigation_result["after_prejudice_remover"]),
        "after_equalized_odds": metric_payload(mitigation_result["after_equalized_odds"]),
        "fairness_score_before": fairness_score_before,
        "fairness_score_after": fairness_score_after,
        "mitigated_candidates": mitigated_candidates,
    }


@router.post("/mitigate/synthetic/{audit_id}", response_model=SyntheticPatchResponse)
def mitigate_with_synthetic_patch(
    audit_id: UUID,
    target_attribute: str = Query(default="gender"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    audit = _get_audit_for_user(db, audit_id, current_user.id)
    ordered_candidates = list(audit.candidates)
    if not ordered_candidates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This audit does not contain candidates.")

    reconstructed_df = pd.DataFrame(rebuild_audit_rows(ordered_candidates))
    patch_result = generate_synthetic_counterfactual_patch(
        reconstructed_df,
        target_attribute=target_attribute,
    )
    metrics_before = metric_payload(patch_result["metrics_before"])
    metrics_after = metric_payload(patch_result["metrics_after"])
    fairness_before = calculate_fairness_score(metrics_before)
    fairness_after = calculate_fairness_score(metrics_after)

    current_results = dict(audit.mitigation_results or {})
    current_results["synthetic_patch"] = patch_result
    audit.mitigation_results = current_results

    store_memory(
        db,
        user_id=current_user.id,
        audit=audit,
        stage="synthetic_patch",
        metadata={
            "target_attribute": target_attribute,
            "generated_rows": patch_result["generated_rows"],
            "fairness_lift": round(fairness_after - fairness_before, 2),
        },
    )
    db.commit()

    return {
        "audit_id": audit.id,
        "engine": patch_result["engine"],
        "enabled": bool(patch_result["enabled"]),
        "target_attribute": target_attribute,
        "generated_rows": int(patch_result["generated_rows"]),
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "fairness_lift": round(fairness_after - fairness_before, 2),
        "reason": patch_result.get("reason"),
        "preview": patch_result.get("preview", []),
    }


@router.get("/report/{audit_id}")
def download_report(
    audit_id: UUID,
    epsilon: float = Query(default=1.0, ge=0.1, le=10.0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    audit = _get_audit_for_user(db, audit_id, current_user.id)
    raw_metrics = metric_payload(
        {
            "disparate_impact": audit.disparate_impact,
            "stat_parity_diff": audit.stat_parity_diff,
            "equal_opp_diff": audit.equal_opp_diff,
            "avg_odds_diff": audit.avg_odds_diff,
        }
    )
    flagged_candidates = [candidate for candidate in audit.candidates if candidate.bias_flagged]
    sanitized = sanitize_report_aggregates(
        metrics=raw_metrics,
        total_candidates=audit.total_candidates,
        flagged_candidates=len(flagged_candidates),
        epsilon=epsilon,
    )
    dp_metrics = sanitized["metrics"]
    dp_pass_flags = metric_payload(dp_metrics)["pass_flags"]

    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("FairFlow AI Bias Audit Report", styles["Title"]),
        Spacer(1, 12),
    ]

    metadata_table = Table(
        [
            ["Dataset", audit.dataset_name],
            ["Created At", audit.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")],
            ["Total Candidates (DP)", str(sanitized["total_candidates"])],
            ["Flagged Candidates (DP)", str(sanitized["flagged_candidates"])],
            ["Bias Detected", "Yes" if audit.bias_detected else "No"],
            ["Mitigation Applied", "Yes" if audit.mitigation_applied else "No"],
            ["Differential Privacy Epsilon", f"{epsilon:.2f}"],
        ],
        colWidths=[160, 320],
    )
    metadata_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#0f172a")),
                ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ]
        )
    )
    story.extend([metadata_table, Spacer(1, 18)])

    metric_rows = [
        ["Metric", "Value", "Threshold", "Status"],
        ["Disparate Impact", f"{dp_metrics['disparate_impact']:.4f}", "> 0.80", "PASS" if dp_pass_flags["disparate_impact"] else "FAIL"],
        ["Statistical Parity Difference", f"{dp_metrics['stat_parity_diff']:.4f}", "|x| < 0.10", "PASS" if dp_pass_flags["stat_parity_diff"] else "FAIL"],
        ["Equal Opportunity Difference", f"{dp_metrics['equal_opp_diff']:.4f}", "|x| < 0.10", "PASS" if dp_pass_flags["equal_opp_diff"] else "FAIL"],
        ["Average Odds Difference", f"{dp_metrics['avg_odds_diff']:.4f}", "|x| < 0.10", "PASS" if dp_pass_flags["avg_odds_diff"] else "FAIL"],
    ]
    metrics_table = Table(metric_rows, colWidths=[180, 90, 100, 90])
    metric_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
    ]
    for row_index in range(1, len(metric_rows)):
        status_value = metric_rows[row_index][3]
        row_color = colors.HexColor("#dcfce7") if status_value == "PASS" else colors.HexColor("#fee2e2")
        metric_style.append(("BACKGROUND", (0, row_index), (-1, row_index), row_color))
    metrics_table.setStyle(TableStyle(metric_style))
    story.extend([metrics_table, Spacer(1, 18)])

    gender_rates = compute_group_hire_rates(list(audit.candidates), "gender")
    ethnicity_rates = compute_group_hire_rates(list(audit.candidates), "ethnicity")
    dp_gender_rows = [["Gender", "Hire Rate (DP)"]]
    for group, value in sorted(gender_rates.items()):
        dp_value = sanitize_metric(
            value,
            epsilon=epsilon,
            sensitivity=1.0 / max(audit.total_candidates, 1),
            lower=0.0,
            upper=1.0,
        )
        dp_gender_rows.append([group, f"{dp_value:.4f}"])

    dp_ethnicity_rows = [["Ethnicity", "Hire Rate (DP)"]]
    for group, value in sorted(ethnicity_rates.items()):
        dp_value = sanitize_metric(
            value,
            epsilon=epsilon,
            sensitivity=1.0 / max(audit.total_candidates, 1),
            lower=0.0,
            upper=1.0,
        )
        dp_ethnicity_rows.append([group, f"{dp_value:.4f}"])

    flagged_table = Table(dp_gender_rows + [["", ""], *dp_ethnicity_rows], repeatRows=1, colWidths=[190, 140])
    flagged_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f59e0b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fff7ed")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.extend([Paragraph("Differentially Private Group Snapshot", styles["Heading2"]), Spacer(1, 8), flagged_table])

    certificate_payload = {
        "audit_id": str(audit.id),
        "dataset_name": audit.dataset_name,
        "created_at": audit.created_at.isoformat(),
        "epsilon": round(epsilon, 4),
        "dp_metrics": dp_metrics,
        "total_candidates_dp": sanitized["total_candidates"],
        "flagged_candidates_dp": sanitized["flagged_candidates"],
        "mitigation_applied": bool(audit.mitigation_applied),
    }
    report_hash = compute_report_hash(certificate_payload)
    certificate = AuditCertificate(
        audit_id=audit.id,
        hash_algorithm="sha256",
        report_hash=report_hash,
        epsilon=epsilon,
        payload=certificate_payload,
    )
    db.add(certificate)
    store_memory(
        db,
        user_id=current_user.id,
        audit=audit,
        stage="dp_report",
        metadata={
            "epsilon": round(epsilon, 4),
            "certificate_hash": report_hash,
        },
    )

    document.build(story)
    db.commit()
    buffer.seek(0)

    headers = {"Content-Disposition": f'attachment; filename="{audit.dataset_name.rsplit(".", 1)[0]}_fairflow_report.pdf"'}
    return StreamingResponse(buffer, media_type="application/pdf", headers=headers)


@router.get("/certificate/{audit_id}", response_model=CertificateResponse)
def get_latest_certificate(
    audit_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    audit = _get_audit_for_user(db, audit_id, current_user.id)
    certificate = (
        db.query(AuditCertificate)
        .filter(AuditCertificate.audit_id == audit.id)
        .order_by(AuditCertificate.created_at.desc())
        .first()
    )
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No certificate exists for this audit yet. Generate a report first.",
        )
    return {
        "audit_id": audit.id,
        "hash_algorithm": certificate.hash_algorithm,
        "report_hash": certificate.report_hash,
        "epsilon": certificate.epsilon,
        "payload": certificate.payload,
        "created_at": certificate.created_at,
    }
