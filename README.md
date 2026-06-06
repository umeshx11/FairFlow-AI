# FairFlow AI

FairFlow AI is a full-stack fairness auditing platform for AI-driven hiring, lending, and healthcare workflows. It lets teams upload decision outcome CSVs, measure bias metrics, inspect subject-level explanations, test counterfactual sensitivity, compare mitigation strategies, and export audit-ready PDF reports.

The main application in this repository is the FastAPI + React project in `backend/` and `frontend/`. A separate prototype lives in `unbiased-ai-decision/` and is not required to run the main FairFlow AI app.

If you are looking for the Google-stack submission assets mentioned elsewhere in this repository, see [`unbiased-ai-decision/README.md`](unbiased-ai-decision/README.md). That prototype contains the Firebase, Vertex AI, Gemini, Flutter mobile/web app, guest demo flow, SDG 10.3 framing, user tests, impact story, video script, and deployment scaffold.

## What the project does

- Uploads hiring, lending, and healthcare datasets and computes fairness metrics on observed outcomes
- Trains a local model to generate candidate-level SHAP explanations
- Runs protected-attribute counterfactual checks for individual candidates
- Stores audits, candidates, mitigation results, memory records, and report certificates in PostgreSQL
- Compares three mitigation stages: reweighing, prejudice remover, and equalized odds
- Exports differentially private PDF audit reports and SHA-256 report certificates
- Supports a browser-side WASM precheck before upload for zero-egress metric validation
- Exposes governance and deep-inspection APIs for memory-aware recommendations and proxy analysis

## Mitigation metric snapshot

FairFlow compares mitigation stages side by side instead of assuming every fairness intervention improves the model. On the repository sample dataset (`sample_candidates.csv`, 200 rows), the current mitigation pipeline produces the following measured deltas.

Thresholds used in the platform: Disparate Impact `> 0.80`; Statistical Parity Difference, Equal Opportunity Difference, and Average Odds Difference `|x| < 0.10`.

| Stage | Disparate Impact | Stat. Parity Diff | Equal Opp. Diff | Avg. Odds Diff | Fairness Score |
| --- | --- | --- | --- | --- | --- |
| Original | `0.6585` | `-0.1556` | `0.0000` | `0.0000` | `50/100` |
| After Reweighing | `0.6585` | `-0.1556` | `0.0000` | `0.0000` | `50/100` |
| After Prejudice Remover | `0.6923` | `-0.1333` | `-0.1220` | `0.0744` | `25/100` |
| After Equalized Odds | `0.0000` | `-0.4556` | `-1.0000` | `0.5678` | `0/100` |

This is exactly why the product keeps all three stages visible: some mitigations improve one metric while hurting another, and some fail outright on a given dataset. The value is not just "apply mitigation" - it is being able to audit the mitigation itself before release.

## Stack

- Backend: FastAPI, SQLAlchemy, PostgreSQL, scikit-learn, SHAP, Fairlearn, AIF360, DoWhy, LangGraph
- Frontend: React 18, Tailwind CSS, Recharts, Headless UI
- Local precheck: C++/WebAssembly bundle built with Emscripten
- Containers: Docker Compose

## Repository layout

```text
FairFlow-AI/
|-- backend/
|-- frontend/
|-- docs/
|-- sample_candidates.csv
|-- docker-compose.yml
|-- README.md
`-- unbiased-ai-decision/
```

## Supported domains

| Domain | Outcome column | Protected attributes | Sample file |
| --- | --- | --- | --- |
| Hiring | `hired` | `gender`, `ethnicity`, `age` | `sample_candidates.csv` |
| Lending | `loan_approved` | `gender`, `race`, `age` | `sample_loan_applications.csv` |
| Healthcare | `admitted` | `gender`, `race`, `age`, `insurance_type` | `sample_medical_admissions.csv` |

## Dataset format

FairFlow now supports three preset schemas plus a custom mapping mode.

### Hiring schema

Required columns:

- `name`
- `gender`
- `age`
- `ethnicity`
- `years_experience`
- `education_level`
- `hired`

Optional columns:

- `skills`
- `previous_companies`

### Lending schema

Required columns:

- `applicant_id`
- `gender`
- `race`
- `age`
- `income`
- `credit_score`
- `loan_amount`
- `employment_years`
- `debt_to_income`
- `loan_approved`

### Healthcare schema

Required columns:

- `patient_id`
- `gender`
- `race`
- `age`
- `insurance_type`
- `severity_score`
- `wait_time_hours`
- `prior_visits`
- `distance_km`
- `admitted`

Sample datasets included in the repository:

- [`sample_candidates.csv`](sample_candidates.csv)
- [`sample_loan_applications.csv`](sample_loan_applications.csv)
- [`sample_medical_admissions.csv`](sample_medical_admissions.csv)

## Quick start with Docker

1. Clone the repository and move into the project root.

```bash
git clone <your-repo-url>
cd FairFlow-AI
```

2. Create the root environment file used by Docker Compose.

```bash
cp .env.example .env
```

PowerShell equivalent:

```powershell
Copy-Item .env.example .env
```

3. Start the full stack.

```bash
docker compose up --build
```

4. Open the app:

- Frontend: `http://localhost:3000`
- Backend health check: `http://localhost:8000/`
- FastAPI docs: `http://localhost:8000/docs`

Notes:

- PostgreSQL runs on port `5432`
- Backend tables are created automatically on startup
- Docker service and database names still use some legacy `fairlens` naming internally

## Local development

### Backend

1. Create the backend environment file.

```bash
cp backend/.env.example backend/.env
```

PowerShell equivalent:

```powershell
Copy-Item backend/.env.example backend/.env
```

2. Install dependencies and run FastAPI.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

On PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

### Frontend

1. Install dependencies and start the React app.

```bash
cd frontend
npm install
npm start
```

2. Rebuild the WASM precheck bundle only if you need to regenerate it.

```bash
npm run build:wasm
```

WASM notes:

- `npm run build:wasm` requires Bash plus Emscripten `em++`
- On Windows, run it from Git Bash or WSL
- Generated files are written to `frontend/public/wasm/`
- The repo already includes a built WASM bundle, so the UI can run without rebuilding it

## Environment variables

### Root `.env`

Used by `docker compose`.

```env
DB_URL=postgresql://fairlens:fairlens@postgres:5432/fairlens
SECRET_KEY=change-me-in-production
POSTGRES_USER=fairlens
POSTGRES_PASSWORD=fairlens
POSTGRES_DB=fairlens
CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://eco-crow-439708-k8.web.app,https://eco-crow-439708-k8.firebaseapp.com
```

### `backend/.env`

Used when running the backend directly.

```env
DATABASE_URL=postgresql://user:password@localhost:5432/fairlens
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://eco-crow-439708-k8.web.app,https://eco-crow-439708-k8.firebaseapp.com
```

## Frontend routes

- `/login`
- `/register`
- `/dashboard`
- `/audit`
- `/candidates/:auditId`
- `/mitigate/:auditId`

## API overview

Authentication:

- `POST /auth/register`
- `POST /auth/login`

Audit workflow:

- `POST /audit/upload`
- `GET /audit/list`
- `GET /audit/{audit_id}`
- `GET /domain/templates`

Candidate review:

- `GET /candidates/{audit_id}`
- `GET /explain/{candidate_id}`
- `POST /counterfactual`

Mitigation and reporting:

- `POST /mitigate/{audit_id}`
- `GET /report/{audit_id}`
- `GET /certificate/{audit_id}`

Advanced analysis:

- `POST /governance/auditor/{audit_id}`
- `POST /inspection/deep/{audit_id}`

## Example API flow

Register:

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@fairflow.ai",
    "password": "SecurePass123",
    "organization": "FairFlow Labs"
  }'
```

Login:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@fairflow.ai",
    "password": "SecurePass123"
  }'
```

Upload an audit:

```bash
curl -X POST http://localhost:8000/audit/upload \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -F "file=@sample_candidates.csv"
```

Run mitigation:

```bash
curl -X POST http://localhost:8000/mitigate/<AUDIT_ID> \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

Download the report:

```bash
curl "http://localhost:8000/report/<AUDIT_ID>?epsilon=1.0" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  --output fairflow_report.pdf
```

## Project notes

- Baseline fairness metrics are calculated from the uploaded `hired` outcomes
- A trained Random Forest model is used for SHAP explanations and counterfactual generation
- Candidate-level counterfactuals test whether changing protected attributes changes the model decision
- Running a report also stores a certificate that can later be fetched from `/certificate/{audit_id}`
- The current UI focuses on dashboard, audit upload, candidate review, and mitigation; deep inspection is available through the backend API

## Additional docs

- [Ethos architecture notes](docs/ethos-architecture.md)
- [WASM core notes](docs/ethos-wasm-core.md)
- [Compliance mapping](docs/ethos-compliance.md)
- [API contracts](docs/ethos-api-contracts.md)
- [Agent prompts](docs/ethos-agent-prompts.md)
