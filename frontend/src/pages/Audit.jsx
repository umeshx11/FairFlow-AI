import { CheckCircle2, ChevronRight, LockKeyhole, Sparkles } from "lucide-react";
import { useState } from "react";
import toast from "react-hot-toast";
import { useNavigate } from "react-router-dom";

import { LAST_AUDIT_STORAGE_KEY, uploadAudit } from "../api/fairlensApi";
import CSVUploader from "../components/CSVUploader";
import FairnessReportCard from "../components/FairnessReportCard";
import LocalWasmPrecheckCard from "../components/LocalWasmPrecheckCard";
import { buildEthosInputFromCsvText } from "../wasm/csvAuditInput";
import { runEthosPipeline } from "../wasm/ethosEngine";
import { sanitizeCsvForUpload } from "../wasm/privacyShield";

const steps = [
  { id: 1, label: "Upload" },
  { id: 2, label: "Analyzing" },
  { id: 3, label: "Results" }
];

function Audit() {
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [activeStep, setActiveStep] = useState(1);
  const [localPrecheck, setLocalPrecheck] = useState(null);
  const [proxyColumn, setProxyColumn] = useState("years_experience");
  const [privacySummary, setPrivacySummary] = useState(null);

  const handleUpload = async (file) => {
    setUploading(true);
    setActiveStep(2);
    let csvText = "";

    try {
      csvText = await file.text();
      const localInput = buildEthosInputFromCsvText(csvText, {
        proxyColumn: "years_experience"
      });
      const localResult = await runEthosPipeline(localInput);
      setLocalPrecheck(localResult);
      setProxyColumn(localInput.proxyColumn);
    } catch (error) {
      setLocalPrecheck(null);
      setProxyColumn("years_experience");
    }

    const formData = new FormData();
    let privacyStats = null;
    try {
      const sanitized = await sanitizeCsvForUpload(csvText || (await file.text()));
      privacyStats = sanitized.stats;
      setPrivacySummary(privacyStats);
      const sanitizedFile = new File([sanitized.csvText], file.name, {
        type: "text/csv"
      });
      formData.append("file", sanitizedFile);
    } catch (error) {
      setPrivacySummary(null);
      formData.append("file", file);
    }

    try {
      const response = await uploadAudit(formData);
      setReport(response);
      setActiveStep(3);
      localStorage.setItem(LAST_AUDIT_STORAGE_KEY, response.audit.id);
      toast.success(
        `Upload completed. ${response?.summary?.total_candidates ?? 0} candidates analyzed${
          privacyStats && privacyStats.fieldsHashed > 0
            ? `, ${privacyStats.fieldsHashed} PII fields hashed locally`
            : ""
        }.`
      );
      return response;
    } catch (error) {
      setActiveStep(1);
      throw error;
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="section-card overflow-hidden bg-[linear-gradient(135deg,#fff7ed_0%,#ffffff_48%,#eff6ff_100%)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-amber-dark">New Audit</p>
            <h1 className="mt-4 text-4xl font-extrabold text-slate-900">Upload a hiring dataset for review</h1>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">
              FairFlow AI will train a hiring decision model, compute fairness metrics, generate
              candidate explanations, and flag protected-attribute counterfactual risks.
            </p>
            <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">
              <LockKeyhole className="h-4 w-4" />
              Zero Data Egress: Local Browser Fairness Precheck
            </div>
          </div>
          <div className="rounded-3xl bg-navy p-5 text-white shadow-glow">
            <div className="flex items-center gap-3">
              <Sparkles className="h-6 w-6 text-amber-light" />
              <div>
                <p className="text-sm font-semibold">Audit Workflow</p>
                <p className="text-sm text-slate-300">CSV upload to mitigation-ready results</p>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-wrap gap-4">
          {steps.map((step, index) => {
            const isComplete = activeStep > step.id;
            const isActive = activeStep === step.id;
            return (
              <div key={step.id} className="flex items-center gap-4">
                <div
                  className={`flex h-12 w-12 items-center justify-center rounded-full border-2 text-sm font-bold ${
                    isComplete
                      ? "border-emerald-500 bg-emerald-500 text-white"
                      : isActive
                        ? "border-amber bg-amber/10 text-amber-dark"
                        : "border-slate-200 bg-white text-slate-400"
                  }`}
                >
                  {isComplete ? <CheckCircle2 className="h-5 w-5" /> : step.id}
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">{step.label}</p>
                </div>
                {index < steps.length - 1 && <ChevronRight className="h-4 w-4 text-slate-300" />}
              </div>
            );
          })}
        </div>
      </div>

      <CSVUploader onUpload={handleUpload} uploading={uploading} />
      {privacySummary && (
        <section className="section-card border border-emerald-200 bg-emerald-50/60">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-emerald-700">Privacy Shield</p>
          <h3 className="mt-2 text-2xl font-bold text-slate-900">Local PII hashing applied before upload</h3>
          <p className="mt-3 text-sm leading-7 text-slate-700">
            Rows processed: <span className="font-semibold">{privacySummary.rowsProcessed}</span> • Fields hashed:{" "}
            <span className="font-semibold">{privacySummary.fieldsHashed}</span>
          </p>
          {privacySummary.columnsHashed?.length > 0 && (
            <p className="mt-2 text-sm text-slate-700">
              Columns protected:{" "}
              <span className="font-semibold">{privacySummary.columnsHashed.join(", ")}</span>
            </p>
          )}
        </section>
      )}
      <LocalWasmPrecheckCard result={localPrecheck} proxyColumn={proxyColumn} />

      {!report && (
        <div className="section-card text-center">
          <h2 className="text-2xl font-bold text-slate-900">Waiting for a dataset</h2>
          <p className="mt-3 text-sm leading-7 text-slate-500">
            Drop a CSV above to generate fairness metrics, candidate-level SHAP explanations, and
            a full mitigation-ready bias report.
          </p>
        </div>
      )}

      {report && (
        <>
          <FairnessReportCard metrics={report.metrics} />

          <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
            <div className="section-card">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Summary</p>
              <h3 className="mt-2 text-2xl font-bold text-slate-900">Audit completed successfully</h3>
              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                  <p className="text-sm font-medium text-slate-500">Candidates analyzed</p>
                  <p className="mt-2 text-3xl font-extrabold text-slate-900">{report.summary.total_candidates}</p>
                </div>
                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                  <p className="text-sm font-medium text-slate-500">Bias flags found</p>
                  <p className="mt-2 text-3xl font-extrabold text-slate-900">{report.summary.bias_flags}</p>
                </div>
              </div>
              <div className="mt-6 rounded-3xl bg-amber/10 p-5 text-sm leading-7 text-slate-700">
                This dataset scored {Math.round(report.audit.fairness_score)} out of 100. You can
                move into candidate review or immediately compare mitigation strategies.
              </div>
              {report.summary?.cultural_scan && (
                <div className="mt-6 rounded-3xl border border-indigo-200 bg-indigo-50 p-5 text-sm leading-7 text-slate-700">
                  IndiCASA cultural scan:{" "}
                  <span className="font-semibold">
                    {report.summary.cultural_scan.high_risk_count}
                  </span>{" "}
                  high-risk dimension(s) detected ({report.summary.cultural_scan.engine}).
                </div>
              )}
            </div>

            <div className="section-card">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Next Actions</p>
              <h3 className="mt-2 text-2xl font-bold text-slate-900">Choose how to continue</h3>
              <div className="mt-6 grid gap-4 md:grid-cols-2">
                <button
                  type="button"
                  onClick={() => navigate(`/mitigate/${report.audit.id}`)}
                  className="rounded-3xl bg-navy p-6 text-left text-white transition hover:bg-navy-light"
                >
                  <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-light">
                    Mitigation Center
                  </p>
                  <h4 className="mt-3 text-2xl font-bold">Apply Mitigation</h4>
                  <p className="mt-3 text-sm leading-7 text-slate-300">
                    Run all three mitigation strategies and compare the fairness uplift before
                    modifying rankings.
                  </p>
                </button>
                <button
                  type="button"
                  onClick={() => navigate(`/candidates/${report.audit.id}`)}
                  className="rounded-3xl border border-slate-200 bg-white p-6 text-left transition hover:border-amber/50 hover:bg-amber/5"
                >
                  <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">
                    Candidate Explorer
                  </p>
                  <h4 className="mt-3 text-2xl font-bold text-slate-900">View Candidates</h4>
                  <p className="mt-3 text-sm leading-7 text-slate-600">
                    Drill into SHAP explanations, proxy risk flags, and candidate counterfactuals.
                  </p>
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default Audit;
