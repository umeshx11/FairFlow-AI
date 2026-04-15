from io import BytesIO
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session, joinedload

from database import get_db
from ml.mitigator import apply_mitigations
from models import Audit, User
from routers.auth import get_current_user
from schemas import MitigationResponse
from utils import calculate_fairness_score, metric_payload, rebuild_audit_rows


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

    final_predictions = mitigation_result.get("final_predictions", [])
    for index, candidate in enumerate(ordered_candidates):
        if index < len(final_predictions):
            candidate.mitigated_decision = bool(final_predictions[index])

    audit.mitigation_applied = True
    audit.mitigation_results = {
        "original": mitigation_result["original"],
        "after_reweighing": mitigation_result["after_reweighing"],
        "after_prejudice_remover": mitigation_result["after_prejudice_remover"],
        "after_equalized_odds": mitigation_result["after_equalized_odds"],
    }
    db.commit()

    fairness_score_before = calculate_fairness_score(mitigation_result["original"])
    fairness_score_after = calculate_fairness_score(mitigation_result["after_equalized_odds"])
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


@router.get("/report/{audit_id}")
def download_report(
    audit_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    audit = _get_audit_for_user(db, audit_id, current_user.id)
    metrics = metric_payload(
        {
            "disparate_impact": audit.disparate_impact,
            "stat_parity_diff": audit.stat_parity_diff,
            "equal_opp_diff": audit.equal_opp_diff,
            "avg_odds_diff": audit.avg_odds_diff,
        }
    )

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
            ["Total Candidates", str(audit.total_candidates)],
            ["Bias Detected", "Yes" if audit.bias_detected else "No"],
            ["Mitigation Applied", "Yes" if audit.mitigation_applied else "No"],
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
        ["Disparate Impact", f"{metrics['disparate_impact']:.4f}", "> 0.80", "PASS" if metrics["pass_flags"]["disparate_impact"] else "FAIL"],
        ["Statistical Parity Difference", f"{metrics['stat_parity_diff']:.4f}", "|x| < 0.10", "PASS" if metrics["pass_flags"]["stat_parity_diff"] else "FAIL"],
        ["Equal Opportunity Difference", f"{metrics['equal_opp_diff']:.4f}", "|x| < 0.10", "PASS" if metrics["pass_flags"]["equal_opp_diff"] else "FAIL"],
        ["Average Odds Difference", f"{metrics['avg_odds_diff']:.4f}", "|x| < 0.10", "PASS" if metrics["pass_flags"]["avg_odds_diff"] else "FAIL"],
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

    flagged_candidates = sorted(
        [candidate for candidate in audit.candidates if candidate.bias_flagged],
        key=lambda candidate: float((candidate.counterfactual_result or {}).get("confidence", 0.0)),
        reverse=True,
    )[:10]

    flagged_rows = [["Name", "Gender", "Ethnicity", "Decision", "Confidence", "Proxy Flags"]]
    for candidate in flagged_candidates:
        flagged_rows.append(
            [
                candidate.name,
                candidate.gender,
                candidate.ethnicity,
                "Hired" if candidate.original_decision else "Rejected",
                f"{float((candidate.counterfactual_result or {}).get('confidence', 0.0)):.2f}",
                ", ".join((candidate.shap_values or {}).get("proxy_flags", [])) or "None",
            ]
        )

    flagged_table = Table(flagged_rows, repeatRows=1, colWidths=[110, 70, 90, 65, 65, 120])
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
    story.extend([Paragraph("Top 10 Flagged Candidates", styles["Heading2"]), Spacer(1, 8), flagged_table])

    document.build(story)
    buffer.seek(0)

    headers = {"Content-Disposition": f'attachment; filename="{audit.dataset_name.rsplit(".", 1)[0]}_fairflow_report.pdf"'}
    return StreamingResponse(buffer, media_type="application/pdf", headers=headers)
