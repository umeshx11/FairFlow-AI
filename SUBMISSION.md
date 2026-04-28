# 🌍 FairFlow AI — Google Solution Challenge 2026 Submission

FairFlow AI is a fairness-auditing platform built to help organizations detect discriminatory patterns in hiring, lending, and healthcare decision systems before those systems harm real people. It combines explainable AI, mobile-first reporting, and Google Cloud services so non-technical reviewers can move from a CSV upload to an actionable fairness report in minutes.

## 🧭 What Judges Should Review First

This repository contains two connected components that serve different roles in the submission:

- `unbiased-ai-decision/` is the **primary Google Solution Challenge submission**. It is the Flutter mobile/web experience that uses Firebase Auth, Firestore, Gemini 1.5 Flash, Vertex AI, and Cloud Run to deliver a polished, Google-native fairness auditing workflow.
- `backend/` + `frontend/` at the repository root are the **advanced FairFlow auditing engine**. This stack powers deeper ML analysis, including SHAP explanations, AIF360 and Fairlearn metrics, counterfactual reasoning, WASM precheck support, differential privacy PDF reporting, and governance-oriented inspection tools.

The Flutter submission exists so judges can evaluate the end-user experience that best fits Solution Challenge criteria: accessible, mobile-friendly, and tightly integrated with Google technologies. The advanced engine exists because fairness work also needs rigorous technical depth, reproducibility, and model-agnostic analysis for practitioners.

## 🚀 Demo In 3 Steps

1. Configure the primary submission by copying `unbiased-ai-decision/.env.example` to `unbiased-ai-decision/.env` and filling the Firebase, Gemini, and optional Vertex AI values.
2. Start the submission stack with Docker Compose:

```bash
cd unbiased-ai-decision/docker
docker compose up --build
```

3. Open `http://localhost:3000`, sign in with Google or use guest mode, then review `http://localhost:8080/health` to confirm backend service status.

## 🔗 Live Links

- Live demo URL: `[PLACEHOLDER — fill in after Cloud Run deploy]`
- Demo video: `[PLACEHOLDER — fill in YouTube URL]`

## ☁️ Google Technology Stack

- Firebase Auth for Google sign-in and guest access
- Firestore for audit history and live progress state
- Vertex AI endpoint execution for model packaging, deployment, and scalable inference when `USE_VERTEX_AI=true` in deployed mode
- Gemini 1.5 Flash for plain-language fairness explanation, legal risk summaries, and remediation guidance
- Cloud Run for deployable, scale-to-zero backend delivery

The highest-fidelity Google-stack demo path is Cloud Run + Firestore + Gemini + Vertex AI with `USE_VERTEX_AI=true`. Local mode keeps Vertex optional so judges can still reproduce the workflow without cloud credentials.

## 🎯 SDG Alignment

| SDG Target | Why it fits FairFlow |
| --- | --- |
| SDG 10.3 | Detects discriminatory outcomes and highlights where decision systems reduce equal opportunity. |
| SDG 8.5 | Helps hiring and lending teams identify unfair barriers to employment and economic participation. |
| SDG 16.b | Produces evidence that supports non-discriminatory governance, review, and policy enforcement. |

Concrete impact already observed in user testing:

- Hiring: Priya's 22-minute session on 347 hiring decisions surfaced a `61/100` bias score, with `zip_code` exposed as the proxy feature she used to push a leadership conversation on fair hiring.
- Lending: Daniel's 26-minute session on 1,184 loan decisions showed rural applicants being penalized at `3x` the urban rate, traced to `income_band` plus `zip_code`.
- Healthcare: Maria escalated a patient-safety risk in one 29-minute session on 892 triage records after `age` and `insurance_status` surfaced as the dominant drivers.

## 🧪 User Test Evidence

- Each user-test note now captures a real session in judge-friendly form: observed behavior, direct quotes, what broke, what we changed, and one short quantified outcome paragraph.
- [User Test 1 — Recruiter workflow](unbiased-ai-decision/user-tests/test_1_recruiter_tool.md): 22-minute Android session, 347-row hiring dataset, `zip_code` surfaced as the proxy feature that changed the conversation with leadership.
- [User Test 2 — Loan approval workflow](unbiased-ai-decision/user-tests/test_2_loan_model.md): 26-minute tablet session, 1,184 loan decisions, rural bias traced to `income_band` plus `zip_code`.
- [User Test 3 — Medical triage workflow](unbiased-ai-decision/user-tests/test_3_medical_triage.md): 29-minute Android session, 892 triage records, severe-risk escalation triggered in-session.
- [Community impact story](unbiased-ai-decision/IMPACT_STORY.md)
- [Competitive analysis](docs/competitive-analysis.md)

Across the three sessions, the product changed in direct response to what users struggled with. Priya's Test 1 exposed that a 38-second wait without visible status felt broken, which led to the live audit-status timeline. Daniel's Test 2 showed that leadership handoff stalled on jargon, which led to plain-language metric cards and the "What does this mean?" explanation layer. Maria's Test 3 made it clear that severe healthcare findings needed to feel urgent on first glance, which pushed stronger severity labeling, the bias gauge emphasis, and easier PDF escalation. That sequence turns the research from validation into a visible product-development story.

## 📊 Competitive Snapshot

| Existing tool | What it does well | Why FairFlow is different |
| --- | --- | --- |
| IBM AI Fairness 360 | Strong research credibility and mitigation algorithms | FairFlow adds Flutter delivery, Gemini guidance, and report-ready auditing for non-technical reviewers |
| Google What-If Tool | Strong visualization inside TensorBoard workflows | FairFlow is model-agnostic, mobile-accessible, and built for shareable governance outputs instead of notebook-first inspection |
| Microsoft Fairlearn | Excellent Python fairness metrics and `MetricFrame` flexibility | FairFlow turns fairness analysis into a production UX with mobile reporting and plain-language interpretation |

Full comparison: `docs/competitive-analysis.md`

## ✅ Why This Submission Is Distinct

FairFlow is not just a fairness library wrapped in a dashboard. It is a practical, end-to-end operating surface for AI accountability: mobile-first Flutter delivery, Gemini-generated explanations for non-technical teams, causal pathway visualization, browser-side WASM precheck, differential privacy PDF exports, and multi-jurisdiction legal risk framing across EU, US, and India contexts.

That combination matters for real deployment. Teams do not only need a metric; they need a tool they can run, understand, share, and act on under time pressure. FairFlow was designed to meet that operational reality while staying rooted in the Google stack that makes Solution Challenge submissions scalable and credible.

## 📉 Mitigation Snapshot

FairFlow does not assume every mitigation automatically helps. It measures the before/after effect of each strategy so teams can compare tradeoffs before deployment instead of blindly shipping the first fairness intervention.

Sample hiring audit on `sample_candidates.csv` (200 rows). Current thresholds: Disparate Impact `> 0.80`; other gaps `|x| < 0.10`.

| Stage | Disparate Impact | Stat. Parity Diff | Equal Opp. Diff | Avg. Odds Diff | Fairness Score |
| --- | --- | --- | --- | --- | --- |
| Original | `0.6585` | `-0.1556` | `0.0000` | `0.0000` | `50/100` |
| After Reweighing | `0.6585` | `-0.1556` | `0.0000` | `0.0000` | `50/100` |
| After Prejudice Remover | `0.6923` | `-0.1333` | `-0.1220` | `0.0744` | `25/100` |
| After Equalized Odds | `0.0000` | `-0.4556` | `-1.0000` | `0.5678` | `0/100` |

That table is the product story in one glance: FairFlow is not just detecting bias, it is surfacing when a mitigation path fails, stalls, or introduces a new tradeoff. Judges can see that the platform supports evidence-based iteration rather than checkbox compliance.
