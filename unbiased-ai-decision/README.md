# Unbiased AI Decision

AI fairness auditing for automated decisions in hiring, lending, and care delivery.

![SDG 10](https://img.shields.io/badge/SDG%2010-Reduced%20Inequalities-009EDB?style=for-the-badge)
![Firebase](https://img.shields.io/badge/Firebase-FFCA28?style=for-the-badge&logo=firebase&logoColor=black)
![Vertex AI](https://img.shields.io/badge/Vertex%20AI-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-8E75FF?style=for-the-badge&logo=googlebard&logoColor=white)
![Flutter](https://img.shields.io/badge/Flutter-02569B?style=for-the-badge&logo=flutter&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SHAP](https://img.shields.io/badge/SHAP-Explainability-EF4444?style=for-the-badge)
![Causal AI](https://img.shields.io/badge/Causal%20AI-Enabled-111827?style=for-the-badge)

## SDG Targets

Primary alignment: **SDG 10 - Reduced Inequalities**  
Target 10.3: **Ensure equal opportunity and reduce inequalities of outcome, including by eliminating discriminatory practices**

Additional live mappings returned by the backend:

- **SDG 8.5** - Equal access to productive employment and equal pay for equal work
- **SDG 16.b** - Non-discriminatory laws, policies, and enforcement

## Evidence Checklist

- Google tech integration: Firebase Auth, Firestore, Vertex AI, and Gemini integration are implemented in `backend/` and `flutter-app/`
- Flutter mobile app: the product is a Flutter mobile/web app in [`flutter-app/`](flutter-app)
- Demo-ready guest mode: the app can run as a true local guest demo without Firebase web config, while still supporting Firebase-backed guest and Google sign-in flows when configured
- 3 documented user tests: see [`user-tests/test_1_recruiter_tool.md`](user-tests/test_1_recruiter_tool.md), [`user-tests/test_2_loan_model.md`](user-tests/test_2_loan_model.md), and [`user-tests/test_3_medical_triage.md`](user-tests/test_3_medical_triage.md)
- SDG targets cited by number: SDG 10.3, SDG 8.5, and SDG 16.b are surfaced in the UI, backend payloads, and documentation
- Community impact story: see [`IMPACT_STORY.md`](IMPACT_STORY.md)
- Problem statement video: the script is included in [`video_script.md`](video_script.md)
- Docker reproducibility: see [`docker/docker-compose.yml`](docker/docker-compose.yml)
- Deployment scaffold: Cloud Run deployment commands are included below
- Technical depth: Vertex AI endpoint prediction support, SHAP, fairness metrics, causal graph visualization, live Firestore status updates, and Gemini remediation guidance are all present

## Demo Modes

### Local demo

- Backend: `http://localhost:8080`
- Flutter web: `http://localhost:3000`
- Health check: `http://localhost:8080/health`

Local demo behavior:

- Guest/demo mode works without Firebase web config by using the backend sample audit and local audit storage
- If Firebase Admin credentials are configured, audit records are stored in Firestore; otherwise the backend transparently falls back to a local JSON store
- Vertex AI stays off unless `USE_VERTEX_AI=true`
- Backend audit processing still reports live stages such as `uploading`, `uploaded`, `preparing_features`, `generating_shap`, `generating_gemini`, and `complete`

### Deployed demo

This repository includes deployment scaffolding, but it does **not** ship with a published Cloud Run URL by default. After deployment, replace the placeholder URL in your project materials with the real deployed target.

## Why this project stands out

- Mobile-first accessibility through Flutter for phone, tablet, and web use
- Gemini explanations, remediation recommendations, legal-risk summaries, and audit Q&A
- SHAP feature impact and causal graph visualization for technical reviewers
- SDG 10.3, 8.5, and 16.b mappings tied to concrete fairness thresholds
- User-test evidence across hiring, lending, and medical triage workflows

## Architecture

```text
          +----------------------+
          | Flutter Mobile / Web |
          | Google / Guest Auth  |
          +----------+-----------+
                     |
                     v
             +-------+--------+
             | FastAPI Backend |
             | /audit /health  |
             +-------+--------+
                     |
     +---------------+-----------------+
     |                                 |
     v                                 v
+----+----------------+       +--------+---------+
| Gemini 1.5 Flash    |       | Vertex AI        |
| explanation,        |       | endpoint predict |
| remediation, Q&A    |       | + explanations   |
+----+----------------+       +--------+---------+
     |                                 |
     +---------------+-----------------+
                     |
                     v
              +------+------+ 
              | Firestore   |
              | audit docs  |
              | live stages |
              +-------------+
```

## Repository layout

```text
unbiased-ai-decision/
|-- backend/
|-- flutter-app/
|-- user-tests/
|-- docker/
|-- .env.example
|-- video_script.md
|-- IMPACT_STORY.md
`-- README.md
```

## Local setup

1. Clone the repository.
2. Copy `.env.example` to `.env`.
3. For a local-only demo, keep `USE_VERTEX_AI=false`, leave the cloud placeholders in place, and set `FLUTTER_API_BASE_URL=http://localhost:8080`.
4. For Firebase-backed auth/storage or Gemini/Vertex features, replace the remaining placeholder values with real project credentials.
5. Start the app:

```bash
cd docker
docker compose up --build
```

6. Open the app at `http://localhost:3000`.
7. Open the backend health endpoint at `http://localhost:8080/health` to confirm service status.
8. Use `Try as Guest - no sign-up needed` from the login screen.

Optional sample seeding for Firebase-backed demos:

```bash
python backend/seed_sample_audit.py
```

The backend auto-seeds the local sample audit on startup when Firebase Admin is not configured. Run the seeding command only when you want the `sample_hiring_audit` document written into Firestore.

## Environment variables

See [`.env.example`](.env.example) for the full set. The main groups are:

- Firebase service account and web app config
- Gemini API key
- Vertex AI toggle, project, region, staging bucket, and model bucket
- Flutter backend base URL

## Backend API

- `GET /`
- `GET /health`
- `POST /audit`
- `GET /audit/{audit_id}`
- `GET /audit/history/{user_id}`
- `POST /auth/verify`
- `GET /auth/me`

## Cloud Run deployment

```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/unbiased-ai
gcloud run deploy unbiased-ai \
  --image gcr.io/PROJECT_ID/unbiased-ai \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=...,FIREBASE_API_KEY=...,FIREBASE_APP_ID=...,FIREBASE_MESSAGING_SENDER_ID=...,FIREBASE_PROJECT_ID=...,FIREBASE_AUTH_DOMAIN=...,FIREBASE_STORAGE_BUCKET=...,FIREBASE_CREDENTIALS_JSON=...,USE_VERTEX_AI=true,VERTEX_PROJECT_ID=...,VERTEX_REGION=us-central1,VERTEX_STAGING_BUCKET=...,VERTEX_MODEL_BUCKET=...
```

After deployment, update:

- `FLUTTER_API_BASE_URL`
- your shared demo link
- any README or submission materials that still contain placeholders

## User test evidence

- [User Test 1 - Recruiter workflow](user-tests/test_1_recruiter_tool.md)
- [User Test 2 - Loan approval workflow](user-tests/test_2_loan_model.md)
- [User Test 3 - Medical triage workflow](user-tests/test_3_medical_triage.md)

## Impact and video assets

- [Community impact story](IMPACT_STORY.md)
- [Problem statement video script](video_script.md)

## Roadmap

- CI/CD bias gates for model release approval
- Multi-language support for policy and compliance teams
- Government API integrations for regulated decision audits
- Real-time fairness monitoring dashboards
