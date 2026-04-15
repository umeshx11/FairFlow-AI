# FairLens AI

FairLens AI is a full-stack bias detection and mitigation platform for hiring systems. It lets teams upload hiring outcome datasets, measure fairness risks, inspect candidate-level SHAP explanations, run counterfactual bias checks, compare mitigation strategies, and export audit-ready PDF reports.

## Features

- FastAPI backend with JWT authentication and PostgreSQL persistence
- React 18 frontend with responsive dashboard, audit workflow, candidate explorer, and mitigation center
- Bias metrics powered by scikit-learn, SHAP, aif360, and fairlearn
- Candidate-level explainability with SHAP waterfall views and proxy-feature flags
- Counterfactual analysis that tests protected-attribute sensitivity
- Mitigation pipeline covering reweighing, prejudice remover, and equalized odds post-processing
- Client-side WASM fairness precheck (C++ core) for zero-egress metric validation before upload
- LangGraph-based governance auditor agent with historical memory retrieval
- Deep inspection API using DoWhy causal proxy discovery + TCAV-style concept translation
- Differentially private report export with immutable SHA-256 fairness certificate
- Downloadable PDF bias audit reports
- Docker and docker-compose support for local orchestration

## Prerequisites

- Node.js 18+
- Python 3.10+
- PostgreSQL 15+
- Emscripten (`em++`) for compiling the frontend WASM core (optional but recommended)
- Docker and Docker Compose

## Project Structure

```text
FairLens AI/
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

WASM technical notes: [`docs/ethos-wasm-core.md`](/Users/akshatagrawal/Desktop/FairFlow-AI/docs/ethos-wasm-core.md)
Ethos architecture notes: [`docs/ethos-architecture.md`](/Users/akshatagrawal/Desktop/FairFlow-AI/docs/ethos-architecture.md)
Compliance mapping: [`docs/ethos-compliance.md`](/Users/akshatagrawal/Desktop/FairFlow-AI/docs/ethos-compliance.md)

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

The repository includes [sample_candidates.csv](/Users/akshatagrawal/Desktop/FairFlow-AI/sample_candidates.csv) with 200 seeded records containing intentional hiring bias patterns across gender and ethnicity so you can validate the full workflow immediately.

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
