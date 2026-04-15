from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sqlalchemy.orm import Session

from models import Audit, AuditMemory
from utils import calculate_fairness_score


_EMBEDDING_DIMS = 256
_VECTORIZER = HashingVectorizer(
    n_features=_EMBEDDING_DIMS,
    alternate_sign=False,
    norm=None,
    lowercase=True,
)


@dataclass
class RetrievedMemory:
    memory: AuditMemory
    score: float


def _embed(text: str) -> np.ndarray:
    vector = _VECTORIZER.transform([text]).toarray()[0].astype(np.float32)
    norm = np.linalg.norm(vector)
    if norm <= 1e-9:
        return vector
    return vector / norm


def _to_list(vector: np.ndarray) -> list[float]:
    return vector.astype(float).tolist()


def _metrics_text(audit: Audit) -> str:
    metrics = {
        "disparate_impact": audit.disparate_impact,
        "stat_parity_diff": audit.stat_parity_diff,
        "equal_opp_diff": audit.equal_opp_diff,
        "avg_odds_diff": audit.avg_odds_diff,
    }
    fairness_score = calculate_fairness_score(metrics)
    return (
        f"DI={audit.disparate_impact:.4f}, SPD={audit.stat_parity_diff:.4f}, "
        f"EOD={audit.equal_opp_diff:.4f}, AOD={audit.avg_odds_diff:.4f}, "
        f"fairness={fairness_score:.2f}"
    )


def build_memory_text(
    audit: Audit,
    stage: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    metadata = metadata or {}
    memory_segments = [
        f"stage={stage}",
        f"dataset={audit.dataset_name}",
        f"candidates={audit.total_candidates}",
        _metrics_text(audit),
    ]
    if audit.mitigation_results:
        equalized = audit.mitigation_results.get("after_equalized_odds", {})
        accuracy_delta = float(audit.mitigation_results.get("accuracy_delta_equalized_odds", 0.0))
        fairness_lift = float(audit.mitigation_results.get("fairness_lift_equalized_odds", 0.0))
        equalized_di = float(equalized.get("disparate_impact", audit.disparate_impact) or audit.disparate_impact)
        memory_segments.append(
            f"equalized_odds_di={equalized_di:.4f}"
        )
        memory_segments.append(f"fairness_lift={fairness_lift:.2f}")
        memory_segments.append(f"accuracy_delta={accuracy_delta:.4f}")
    if metadata:
        metadata_items = ", ".join(f"{key}={value}" for key, value in sorted(metadata.items()))
        memory_segments.append(f"meta:{metadata_items}")
    return " | ".join(memory_segments)


def store_memory(
    db: Session,
    *,
    user_id,
    audit: Audit,
    stage: str,
    metadata: dict[str, Any] | None = None,
) -> AuditMemory:
    memory_text = build_memory_text(audit, stage, metadata)
    vector = _embed(memory_text)
    memory = AuditMemory(
        user_id=user_id,
        audit_id=audit.id,
        stage=stage,
        memory_text=memory_text,
        vector=_to_list(vector),
        memory_metadata=metadata or {},
    )
    db.add(memory)
    return memory


def retrieve_memories(
    db: Session,
    *,
    user_id,
    query: str,
    limit: int = 5,
    exclude_audit_id=None,
) -> list[RetrievedMemory]:
    memories = (
        db.query(AuditMemory)
        .filter(AuditMemory.user_id == user_id)
        .order_by(AuditMemory.created_at.desc())
        .all()
    )
    if exclude_audit_id is not None:
        memories = [memory for memory in memories if memory.audit_id != exclude_audit_id]
    if not memories:
        return []

    query_vector = _embed(query)
    hits: list[RetrievedMemory] = []
    for memory in memories:
        raw_vector = np.array(memory.vector or [], dtype=np.float32)
        if raw_vector.size != _EMBEDDING_DIMS:
            raw_vector = _embed(memory.memory_text)
            memory.vector = _to_list(raw_vector)
        norm = np.linalg.norm(raw_vector)
        vector = raw_vector if norm <= 1e-9 else raw_vector / norm
        score = float(np.dot(query_vector, vector))
        hits.append(RetrievedMemory(memory=memory, score=score))

    hits.sort(key=lambda item: item.score, reverse=True)
    return hits[:limit]
