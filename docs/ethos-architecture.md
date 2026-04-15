# Ethos End-to-End Architecture (Points 1-5)

## System Boundaries
- Browser (trusted HR enclave): local CSV parsing, WASM fairness precheck, no third-party egress.
- Backend API (private network): governance orchestration, causal+TCAV inspection, DP reporting.
- PostgreSQL (system of record): audits, candidates, mitigation snapshots, memory vectors, fairness certificates.

## Runtime Components
1. **WASM Fairness Kernel (C++/Emscripten)**
   - Path: `frontend/src/wasm/ethos_core.cpp`
   - Executes DI + Equalized Odds gaps + proxy correlation in one pass.
2. **Auditor Agent (LangGraph + Local RAG)**
   - Paths: `backend/agent/auditor_graph.py`, `backend/agent/memory_store.py`
   - State machine: `Observe -> Analyze -> Act -> Report`
   - Memory table: `audit_memories` (hashed vector embedding + governance metadata).
3. **Deep Inspection (DoWhy + TCAV-style Concepts)**
   - Path: `backend/ml/causal_tcav.py`
   - Detects proxy candidates via causal effect + proxy-strength scoring.
   - Maps model behavior into HR concepts (Leadership, EducationPrestige, TechnicalDepth, OperationalStability).
4. **Differential Privacy + Certificate Layer**
   - Path: `backend/privacy.py`, `backend/routers/mitigation.py`
   - Applies Laplace noise to report aggregates.
   - Creates immutable SHA-256 certificate in `audit_certificates`.

## Data Flow
1. User uploads CSV on `/audit`.
2. Browser runs local WASM precheck before upload.
3. Backend stores full audit and candidate-level artifacts.
4. Optional mitigations create strategy deltas and memory entries.
5. Governance endpoint queries historical memory and emits policy action.
6. Deep inspection endpoint returns causal proxy + concept summaries.
7. Report endpoint emits DP-sanitized PDF + certificate hash.

## Storage Schema Additions
- `audit_memories`: vectorized governance memory for RAG retrieval.
- `audit_certificates`: immutable certificate hash for report payloads.

## Reliability/Latency Notes
- Browser-side metrics reduce server load for first-pass checks.
- Memory retrieval uses local vector similarity (`HashingVectorizer`) without external APIs.
- All sensitive rows stay within trusted browser/backend boundaries; no external model calls required.
