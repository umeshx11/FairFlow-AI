# FairFlow AI (FairLens Dashboard)

FairFlow AI is a privacy-first fairness governance platform for hiring.
In simple words: it checks whether an AI hiring model is unfair, explains why the bias happened, recommends mitigation, and generates compliance-ready audit evidence.

`FairFlow AI` is the platform name used for the Solution Challenge.  
`FairLens` is the product UI/API implementation in this repository.

![Local Privacy Shield Demo](docs/assets/privacy-shield-demo.gif)

## 5 Core Pillars (Implemented)

- [x] **Local-First Privacy Shield (C++/WASM):** PII hashing + precheck in the browser before network upload.
- [x] **Auditor Agent Memory (LangGraph + retrieval):** policy-aware recommendations using historical audits.
- [x] **Deep Inspection (Causal + TCAV):** proxy-path discovery and concept-sensitivity outputs.
- [x] **Differential Privacy + Certificate:** epsilon-controlled report exports and SHA-256 fairness certificate.
- [x] **Multimodal Governance:** video/audio fairness reasoning logs for interview workflow audits.

## Architecture Snapshot

| Layer | Primary Stack | Role |
| :--- | :--- | :--- |
| Edge Privacy | React + C++ WASM | Local PII hashing and fairness precheck (zero raw PII egress) |
| Core Audit | FastAPI + sklearn/fairlearn/aif360 | Metric computation, mitigation, and candidate-level analysis |
| Governance Memory | PostgreSQL + LangGraph | Historical audit recall, drift tracking, and policy-aware recommendations |
| Deep Inspection | DoWhy + TCAV-style translator | Causal proxy discovery and concept-level explainability |
| Reporting & Trust | Differential privacy + SHA-256 | Noise-protected summaries and immutable certificate ledger |

## Features

- FastAPI backend with JWT authentication and PostgreSQL persistence
- React 18 frontend with responsive dashboard, audit workflow, candidate explorer, and mitigation center
- Bias metrics powered by scikit-learn, SHAP, aif360, and fairlearn
- Candidate-level explainability with SHAP waterfall views and proxy-feature flags
- Counterfactual analysis that tests protected-attribute sensitivity
- Mitigation pipeline covering reweighing, prejudice remover, and equalized odds post-processing
- Client-side WASM fairness precheck (C++ core) for zero-egress metric validation before upload
- Local Privacy Shield that hashes PII columns in-browser before CSV upload
- LangGraph-based governance auditor agent with historical memory retrieval
- Deep inspection API using DoWhy causal proxy discovery + TCAV-style concept translation
- IndiCASA-style cultural scan for caste/religion/disability/region/dialect risk gaps
- Synthetic counterfactual patch endpoint for active debiasing ("Debias Now")
- Multimodal audit endpoint for `.mp4`/`.wav` fairness risk screening with reasoning logs
- Differentially private report export with immutable SHA-256 fairness certificate
- Downloadable PDF bias audit reports
- Docker and docker-compose support for local orchestration

## Governance Memory Scalability (AUR-X)

FairLens uses partitioned governance memory retrieval (`M << N`) before vector scoring.  
This allows historical bias-pattern recall across large enterprise audit corpora (10,000+ audits) with low-latency drift detection and real-time recommendation loops.

## Glass Box UI Proof

- **Concept Sensitivity (TCAV):** Deep inspection outputs concept-level sensitivity (`Leadership`, `EducationPrestige`, `TechnicalDepth`, `OperationalStability`) and exposes them for chart rendering in the dashboard.
- **Causal Discovery Trace:** `dag_edges` + `proxy_findings` support both node-link visualization and human-readable policy summaries.
- **Regional Fairness Signal:** The product surfaces IndiCASA-style high-risk dimensions (caste/religion/disability/region/dialect) and includes an **Indic-Bias Certified** badge in the application shell.

## Fairness Definitions

Formal metric definitions are documented in [`docs/fairness-definitions.md`](docs/fairness-definitions.md).

Disparate Impact (`DI`):

\[
\mathrm{DI} = \frac{P(\hat{Y}=1 \mid D=\mathrm{unprivileged})}{P(\hat{Y}=1 \mid D=\mathrm{privileged})}
\]

Statistical Parity Difference (`SPD`):

\[
\mathrm{SPD} = P(\hat{Y}=1 \mid D=\mathrm{unprivileged}) - P(\hat{Y}=1 \mid D=\mathrm{privileged})
\]

## Prerequisites

- Node.js 18+
- Python 3.10+
- PostgreSQL 15+
- Emscripten (`em++`) for compiling the frontend WASM core (optional but recommended)
- Docker and Docker Compose

## Project Structure

```text
FairFlow-AI/
├── backend/
├── frontend/
├── sample_candidates.csv
├── docker-compose.yml
├── .env.example
└── README.md
```

## Setup

1. Clone the repository and move into the project directory.

```bash
git clone <your-repo-url>
cd FairFlow-AI
```

2. Create the root environment file for Docker Compose.

```bash
cp .env.example .env
```

3. Create the backend environment file for local FastAPI runs.

```bash
cp backend/.env.example backend/.env
```

4. Start PostgreSQL, the backend, and the frontend with Docker Compose.

```bash
docker-compose up --build
```

5. If you want to run the React app directly instead of the containerized frontend, install dependencies and start it.

```bash
cd frontend
npm install
npm run build:wasm
npm start
```

`npm run build:wasm` generates `frontend/public/wasm/ethos_core.js` and `frontend/public/wasm/ethos_core.wasm`.  
If this step is skipped, the app automatically falls back to a JS runtime for the local precheck.

WASM technical notes: [`docs/ethos-wasm-core.md`](docs/ethos-wasm-core.md)
Ethos architecture notes: [`docs/ethos-architecture.md`](docs/ethos-architecture.md)
Compliance mapping: [`docs/ethos-compliance.md`](docs/ethos-compliance.md)
Security model: [`SECURITY.md`](SECURITY.md)

6. If you want to run the backend directly instead of the containerized backend, create a virtual environment and install dependencies.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Environment Variables

### Root `.env`

```env
DB_URL=postgresql://fairlens:fairlens@postgres:5432/fairlens
SECRET_KEY=change-me-in-production
POSTGRES_USER=fairlens
POSTGRES_PASSWORD=fairlens
POSTGRES_DB=fairlens
```

### `backend/.env`

```env
DATABASE_URL=postgresql://user:password@localhost:5432/fairlens
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## Sample Dataset

The repository includes [sample_candidates.csv](sample_candidates.csv) with 200 seeded records containing intentional hiring bias patterns across gender and ethnicity so you can validate the full workflow immediately.

## API Endpoints

### Health Check

```bash
curl http://localhost:8000/
```

### Register

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@fairlens.ai",
    "password": "SecurePass123",
    "organization": "FairLens Labs"
  }'
```

### Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@fairlens.ai",
    "password": "SecurePass123"
  }'
```

### Upload Audit CSV

```bash
curl -X POST http://localhost:8000/audit/upload \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -F "file=@sample_candidates.csv"
```

### Upload Multimodal Artifact (`.mp4` / `.wav`)

```bash
curl -X POST http://localhost:8000/audit/upload-multimodal \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -F "file=@interview_clip.mp4" \
  -F "transcript=Candidate discussed village schooling and accent concerns."
```

### List Audits

```bash
curl http://localhost:8000/audit/list \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Get One Audit

```bash
curl http://localhost:8000/audit/<AUDIT_ID> \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Get Candidates

```bash
curl "http://localhost:8000/candidates/<AUDIT_ID>?page=1&page_size=20&search=&bias_status=all" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Get Stored SHAP Explanation

```bash
curl http://localhost:8000/explain/<CANDIDATE_ID> \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Run Counterfactual

```bash
curl -X POST http://localhost:8000/counterfactual \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "candidate_id": "<CANDIDATE_ID>"
  }'
```

### Run Mitigation

```bash
curl -X POST http://localhost:8000/mitigate/<AUDIT_ID> \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Run Synthetic Debias Patch

```bash
curl -X POST "http://localhost:8000/mitigate/synthetic/<AUDIT_ID>?target_attribute=gender" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Download PDF Report

```bash
curl "http://localhost:8000/report/<AUDIT_ID>?epsilon=1.0" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  --output fairlens_report.pdf
```

### Run Governance Auditor Agent

```bash
curl -X POST http://localhost:8000/governance/auditor/<AUDIT_ID> \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Run Deep Inspection (Causal + TCAV)

```bash
curl -X POST http://localhost:8000/inspection/deep/<AUDIT_ID> \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Get Latest Fairness Certificate

```bash
curl http://localhost:8000/certificate/<AUDIT_ID> \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

## Sample Bias Report JSON

```json
{
  "audit": {
    "id": "d3744c84-6f65-4977-a931-c3b54084f61a",
    "user_id": "802b7192-4a8f-4c09-9962-c6af4bb55014",
    "created_at": "2026-04-14T10:28:01.418588",
    "dataset_name": "sample_candidates.csv",
    "total_candidates": 200,
    "disparate_impact": 0.6174,
    "stat_parity_diff": -0.2181,
    "equal_opp_diff": -0.1649,
    "avg_odds_diff": -0.1337,
    "bias_detected": true,
    "mitigation_applied": false,
    "fairness_score": 0,
    "flagged_candidates": 67,
    "gender_hire_rates": {
      "Female": 0.41,
      "Male": 0.67
    },
    "ethnicity_hire_rates": {
      "Asian": 0.69,
      "Black": 0.39,
      "Hispanic": 0.37,
      "White": 0.63
    }
  },
  "metrics": {
    "disparate_impact": 0.6174,
    "stat_parity_diff": -0.2181,
    "equal_opp_diff": -0.1649,
    "avg_odds_diff": -0.1337,
    "pass_flags": {
      "disparate_impact": false,
      "stat_parity_diff": false,
      "equal_opp_diff": false,
      "avg_odds_diff": false
    }
  },
  "summary": {
    "total_candidates": 200,
    "bias_flags": 67,
    "proxy_flags": 19,
    "fairness_score": 0
  }
}
```

## Sample Multimodal Reasoning Log

```json
{
  "analysis_engine": "gemini-adapter-fallback",
  "media_type": "video",
  "file_name": "interview_round2.mp4",
  "risk_score": 76,
  "flagged_concerns": [
    {
      "type": "socioeconomic_proxy_bias",
      "severity": "high",
      "detail": "Interview context may over-weight non-job-relevant environment cues."
    }
  ],
  "reasoning_log": [
    "Bias Detected: Socioeconomic Proxy. The candidate's background contains visual markers of a non-standard office environment (shared room).",
    "Culture-fit score dropped near timestamp 02:14 while technical answer quality stayed stable.",
    "Likely proxy effect: environment marker correlated with ranking change, not Python decorator explanation quality."
  ]
}
```

## Frontend Routes

- `/login`
- `/register`
- `/dashboard`
- `/audit`
- `/candidates/:auditId`
- `/mitigate/:auditId`

## Notes

- The backend creates tables automatically on startup.
- The candidate explorer stores both SHAP results and counterfactual outputs in PostgreSQL.
- Mitigation results update `mitigated_decision` values for the audited candidates.
- The included dataset is intentionally biased so the dashboard and mitigation flow show meaningful deltas immediately.

## Cloud Run Demo Mode (Judge-Friendly)

For competition demos, deploy with a pre-seeded managed database and expose a one-click guest path:
- preload one audited dataset + mitigation snapshots,
- issue a short-lived demo token,
- skip manual database setup during judge evaluation.

Recommended presentation mode for causal discovery:
- **Primary:** node-link DAG view for `protected_attribute -> proxy_feature -> hiring_outcome`.
- **Secondary:** textual summary that explains the top proxy path and policy impact in plain language.

## References

- IBM AI Fairness 360 (AIF360): [https://github.com/Trusted-AI/AIF360](https://github.com/Trusted-AI/AIF360)
- Google Vertex AI documentation: [https://cloud.google.com/vertex-ai/docs](https://cloud.google.com/vertex-ai/docs)
- IndiCASA (IIT Madras, 2025): Intersectional benchmark for Indian-context hiring fairness (`caste`, `religion`, `disability`, `region`, `dialect`) used in FairLens cultural-risk modeling.
