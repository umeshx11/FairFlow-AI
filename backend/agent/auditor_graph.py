from __future__ import annotations

from typing import Any, TypedDict

from sqlalchemy.orm import Session

from agent.memory_store import RetrievedMemory, retrieve_memories
from agent.prompts import ACT_PROMPT, ANALYZE_PROMPT, OBSERVE_PROMPT, REPORT_PROMPT
from models import Audit
from utils import calculate_fairness_score

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except Exception:
    END = "__end__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


class AuditorState(TypedDict, total=False):
    audit_id: str
    observe_summary: str
    retrieved_memories: list[dict[str, Any]]
    recommendation: str
    rationale: str
    actions: list[str]
    stage: str


def _to_memory_payload(items: list[RetrievedMemory]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for item in items:
        payload.append(
            {
                "audit_id": str(item.memory.audit_id) if item.memory.audit_id else None,
                "stage": item.memory.stage,
                "score": round(float(item.score), 4),
                "memory_text": item.memory.memory_text,
                "metadata": item.memory.memory_metadata or {},
            }
        )
    return payload


def _build_observe_summary(audit: Audit) -> str:
    fairness_score = calculate_fairness_score(
        {
            "disparate_impact": audit.disparate_impact,
            "stat_parity_diff": audit.stat_parity_diff,
            "equal_opp_diff": audit.equal_opp_diff,
            "avg_odds_diff": audit.avg_odds_diff,
        }
    )
    return (
        f"{OBSERVE_PROMPT.strip()} Current audit={audit.id}, dataset={audit.dataset_name}, "
        f"DI={audit.disparate_impact:.4f}, SPD={audit.stat_parity_diff:.4f}, "
        f"EOD={audit.equal_opp_diff:.4f}, AOD={audit.avg_odds_diff:.4f}, "
        f"fairness={fairness_score:.2f}, mitigation_applied={audit.mitigation_applied}."
    )


def _choose_strategy(audit: Audit, memories: list[dict[str, Any]]) -> tuple[str, str, list[str]]:
    severe_bias = audit.disparate_impact < 0.8 or abs(audit.equal_opp_diff) >= 0.1
    memory_text = " ".join(item.get("memory_text", "").lower() for item in memories)
    saw_accuracy_drop = "accuracy_delta=-" in memory_text and any(
        token in memory_text for token in ("accuracy_delta=-0.03", "accuracy_delta=-0.04", "accuracy_delta=-0.05")
    )

    if severe_bias and saw_accuracy_drop:
        recommendation = "Prefer constrained reweighing first, then escalate to Equalized Odds only if gaps remain."
        actions = [
            "run_reweighing",
            "evaluate_accuracy_delta_guardrail",
            "run_equalized_odds_if_bias_persists",
        ]
        rationale = (
            f"{ACT_PROMPT.strip()} Retrieved memories show prior mitigation attempts with material accuracy loss, "
            "so strategy is staged to minimize risk."
        )
        return recommendation, rationale, actions

    if severe_bias:
        recommendation = (
            "Disparate Impact is below the 0.8 threshold. Recommend applying Equalized Odds post-processing."
        )
        actions = [
            "run_equalized_odds",
            "review_changed_outcomes",
            "log_certificate_after_mitigation",
        ]
        rationale = (
            f"{ACT_PROMPT.strip()} Bias is above policy tolerance. "
            "Recommendation prioritizes threshold compliance and human review for changed decisions."
        )
        return recommendation, rationale, actions

    recommendation = "No immediate high-risk bias pattern detected. Keep monitoring and re-audit after new hires."
    actions = [
        "monitor_drift_monthly",
        "schedule_next_audit",
    ]
    rationale = (
        f"{ACT_PROMPT.strip()} Current metrics are closer to policy thresholds; recommend governance monitoring."
    )
    return recommendation, rationale, actions


def run_auditor_agent(
    *,
    db: Session,
    audit: Audit,
    user_id,
) -> dict[str, Any]:
    def observe_node(state: AuditorState) -> AuditorState:
        summary = _build_observe_summary(audit)
        return {
            **state,
            "observe_summary": summary,
            "stage": "observe",
        }

    def analyze_node(state: AuditorState) -> AuditorState:
        query = (
            f"{ANALYZE_PROMPT.strip()} "
            f"Find past audits similar to DI={audit.disparate_impact:.4f}, EOD={audit.equal_opp_diff:.4f}, "
            f"mitigation={audit.mitigation_applied}."
        )
        memories = retrieve_memories(
            db,
            user_id=user_id,
            query=query,
            limit=5,
            exclude_audit_id=audit.id,
        )
        return {
            **state,
            "retrieved_memories": _to_memory_payload(memories),
            "stage": "analyze",
        }

    def act_node(state: AuditorState) -> AuditorState:
        recommendation, rationale, actions = _choose_strategy(audit, state.get("retrieved_memories", []))
        return {
            **state,
            "recommendation": recommendation,
            "rationale": rationale,
            "actions": actions,
            "stage": "act",
        }

    def report_node(state: AuditorState) -> AuditorState:
        rationale = state.get("rationale", "")
        report_rationale = f"{REPORT_PROMPT.strip()} {rationale}"
        return {
            **state,
            "rationale": report_rationale,
            "stage": "report",
        }

    initial_state: AuditorState = {
        "audit_id": str(audit.id),
        "stage": "init",
    }

    if LANGGRAPH_AVAILABLE and StateGraph is not None:
        graph = StateGraph(AuditorState)
        graph.add_node("observe", observe_node)
        graph.add_node("analyze", analyze_node)
        graph.add_node("act", act_node)
        graph.add_node("report", report_node)
        graph.set_entry_point("observe")
        graph.add_edge("observe", "analyze")
        graph.add_edge("analyze", "act")
        graph.add_edge("act", "report")
        graph.add_edge("report", END)
        compiled = graph.compile()
        final_state = compiled.invoke(initial_state)
    else:
        final_state = report_node(act_node(analyze_node(observe_node(initial_state))))

    return {
        "audit_id": audit.id,
        "state": final_state.get("stage", "report"),
        "recommendation": final_state.get("recommendation", ""),
        "rationale": final_state.get("rationale", ""),
        "recalled_memories": final_state.get("retrieved_memories", []),
        "actions": final_state.get("actions", []),
    }
