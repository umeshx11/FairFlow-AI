import {
  ArrowRight,
  Download,
  FileSpreadsheet,
  Gauge,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Users
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  LAST_AUDIT_STORAGE_KEY,
  getDemoDatasetDownloadUrl,
  getDemoDatasets,
  listAudits
} from "../api/fairlensApi";
import Spinner from "../components/Spinner";

const scenarioDescriptions = {
  hiring: "Hiring fairness review with candidate-level evidence and selection parity checks.",
  lending: "Loan approval fairness scenario focused on approval-rate variance and exposure gaps.",
  healthcare: "Healthcare admission scenario highlighting patient-group access and pathway differences."
};

const scenarioActions = {
  hiring: "Open candidate review",
  lending: "Open mitigation view",
  healthcare: "Open governance brief"
};

const domainAccent = {
  hiring: "border-blue-200 bg-blue-50 text-blue-700",
  lending: "border-amber-200 bg-amber-50 text-amber-800",
  healthcare: "border-emerald-200 bg-emerald-50 text-emerald-700"
};

function extractErrorMessage(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === "object" && typeof detail.message === "string") {
    return detail.message;
  }
  return fallback;
}

function DemoWorkspace() {
  const [audits, setAudits] = useState([]);
  const [demoDatasets, setDemoDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const fetchWorkspace = async () => {
    setLoading(true);
    setLoadError("");
    try {
      const [auditData, datasetData] = await Promise.all([
        listAudits({ silent: true }),
        getDemoDatasets({ silent: true })
      ]);
      setAudits(auditData);
      setDemoDatasets(datasetData?.datasets || []);
      if (auditData[0]?.id) {
        localStorage.setItem(LAST_AUDIT_STORAGE_KEY, auditData[0].id);
      }
    } catch (error) {
      setAudits([]);
      setDemoDatasets([]);
      setLoadError(extractErrorMessage(error, "Could not load the preview workspace."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkspace();
  }, []);

  const scenarioAudits = useMemo(() => {
    const byDomain = new Map();
    for (const audit of audits) {
      const domain = audit?.domain_config?.domain || "custom";
      if (!byDomain.has(domain)) {
        byDomain.set(domain, audit);
      }
    }
    return ["hiring", "lending", "healthcare"]
      .map((domain) => byDomain.get(domain))
      .filter(Boolean);
  }, [audits]);

  const overview = useMemo(() => {
    const totalCandidates = scenarioAudits.reduce((sum, audit) => sum + (audit.total_candidates || 0), 0);
    const totalFlagged = scenarioAudits.reduce((sum, audit) => sum + (audit.flagged_candidates || 0), 0);
    const averageFairness =
      scenarioAudits.length > 0
        ? Math.round(
            scenarioAudits.reduce((sum, audit) => sum + Number(audit.fairness_score || 0), 0) / scenarioAudits.length
          )
        : 0;
    return {
      totalCandidates,
      totalFlagged,
      averageFairness
    };
  }, [scenarioAudits]);

  if (loading) {
    return (
      <div className="section-card flex min-h-[320px] items-center justify-center">
        <Spinner className="h-8 w-8 text-navy" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {loadError && (
        <div className="section-card border border-rose-200 bg-rose-50/70">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.14em] text-rose-700">Preview unavailable</p>
              <p className="mt-2 text-sm leading-7 text-rose-900">{loadError}</p>
            </div>
            <button
              type="button"
              onClick={fetchWorkspace}
              className="inline-flex w-fit items-center rounded-xl border border-rose-300 bg-white px-4 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-100"
            >
              Retry loading workspace
            </button>
          </div>
        </div>
      )}

      <section className="section-card overflow-hidden bg-[linear-gradient(135deg,#fff7ed_0%,#ffffff_48%,#eff6ff_100%)]">
        <div className="grid gap-8 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-amber-dark">Preview Workspace</p>
            <h1 className="mt-3 text-4xl font-extrabold leading-tight text-slate-900">
              Explore the platform through three preloaded fairness scenarios
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">
              This guided workspace is seeded with hiring, lending, and healthcare audits so you can
              review metrics, candidate signals, mitigation strategies, and governance outputs without
              uploading a dataset first.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              {["Preloaded audits", "Candidate evidence", "Mitigation workflow", "Governance review"].map((item) => (
                <span
                  key={item}
                  className="inline-flex items-center rounded-full border border-amber/20 bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-3xl bg-navy p-6 text-white shadow-glow">
            <div className="flex items-center gap-3">
              <div className="rounded-2xl bg-white/10 p-3 text-amber-light">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">Workspace Snapshot</p>
                <p className="mt-1 text-sm text-slate-300">Seeded from the built-in reference CSV scenarios.</p>
              </div>
            </div>
            <div className="mt-6 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Scenarios</p>
                <p className="mt-3 text-3xl font-bold text-white">{scenarioAudits.length}</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Average Score</p>
                <p className="mt-3 text-3xl font-bold text-white">{overview.averageFairness} / 100</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Records Included</p>
                <p className="mt-3 text-3xl font-bold text-white">{overview.totalCandidates}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <div className="section-card">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-amber/10 p-3 text-amber-dark">
              <FileSpreadsheet className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Included data</p>
              <p className="mt-1 text-sm text-slate-600">Three benchmark audits seeded for review.</p>
            </div>
          </div>
        </div>
        <div className="section-card">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-blue-100 p-3 text-blue-700">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-700">Candidate drilldown</p>
              <p className="mt-1 text-sm text-slate-600">Inspect flagged records and explanation evidence.</p>
            </div>
          </div>
        </div>
        <div className="section-card">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-emerald-100 p-3 text-emerald-700">
              <Scale className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-emerald-700">Governance output</p>
              <p className="mt-1 text-sm text-slate-600">Review mitigation and policy-facing recommendations.</p>
            </div>
          </div>
        </div>
      </section>

      <section className="section-card border border-slate-200 bg-white">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Default CSV Files</p>
            <h2 className="mt-2 text-3xl font-extrabold text-slate-900">Download the source datasets used in the demo</h2>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">
              These are the original reference CSV files behind the preview workspace, available if you want to
              inspect the schema or run the same scenarios through the upload flow yourself.
            </p>
          </div>
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-3">
          {demoDatasets.map((dataset) => (
            <div key={dataset.reference_dataset_name} className="rounded-3xl border border-slate-200 bg-slate-50/70 p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${domainAccent[dataset.domain] || "border-slate-200 bg-slate-100 text-slate-700"}`}>
                    {dataset.display_name}
                  </span>
                  <h3 className="mt-4 text-xl font-bold text-slate-900">{dataset.reference_dataset_name}</h3>
                  <p className="mt-2 text-sm leading-7 text-slate-600">{dataset.summary}</p>
                </div>
                <div className="rounded-2xl bg-white p-3 text-amber-dark shadow-sm">
                  <FileSpreadsheet className="h-5 w-5" />
                </div>
              </div>

              <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Used by preview audit</p>
                <p className="mt-2 text-sm font-medium text-slate-800">{dataset.seed_dataset_name}</p>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <a
                  href={getDemoDatasetDownloadUrl(dataset.reference_dataset_name)}
                  download={dataset.reference_dataset_name}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl bg-navy px-4 py-3 text-sm font-semibold text-white transition hover:bg-navy-light"
                >
                  <Download className="h-4 w-4" />
                  Download CSV
                </a>
                <Link
                  to="/audit"
                  className="inline-flex items-center justify-center rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-amber hover:text-amber-dark"
                >
                  Open upload flow
                </Link>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="section-card border border-slate-200 bg-white">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Scenario Library</p>
            <h2 className="mt-2 text-3xl font-extrabold text-slate-900">Choose a demo path</h2>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">
              Each scenario opens into the same production workflow used by uploaded datasets, so you can
              jump straight into candidate review, mitigation analysis, or governance.
            </p>
          </div>
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-amber hover:text-amber-dark"
          >
            Open full dashboard
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-3">
          {scenarioAudits.map((audit) => {
            const domain = audit?.domain_config?.domain || "custom";
            const fairnessScore = Math.round(Number(audit?.fairness_score || 0));
            const badgeTone = audit?.bias_detected
              ? "border-amber-200 bg-amber-50 text-amber-800"
              : "border-emerald-200 bg-emerald-50 text-emerald-700";
            const StatusIcon = audit?.bias_detected ? ShieldAlert : ShieldCheck;

            return (
              <div key={audit.id} className="rounded-3xl border border-slate-200 bg-slate-50/70 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${domainAccent[domain] || "border-slate-200 bg-slate-100 text-slate-700"}`}>
                      {audit?.domain_config?.display_name || domain}
                    </span>
                    <h3 className="mt-4 text-2xl font-bold text-slate-900">{audit?.domain_config?.display_name || domain}</h3>
                    <p className="mt-2 text-sm leading-7 text-slate-600">
                      {scenarioDescriptions[domain] || "Preloaded fairness scenario for guided evaluation."}
                    </p>
                  </div>
                  <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${badgeTone}`}>
                    <StatusIcon className="h-3.5 w-3.5" />
                    {audit?.bias_detected ? "Bias flagged" : "Within range"}
                  </div>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="flex items-center gap-2 text-slate-500">
                      <Gauge className="h-4 w-4" />
                      <p className="text-xs font-semibold uppercase tracking-[0.16em]">Score</p>
                    </div>
                    <p className="mt-3 text-2xl font-bold text-slate-900">{fairnessScore} / 100</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="flex items-center gap-2 text-slate-500">
                      <Users className="h-4 w-4" />
                      <p className="text-xs font-semibold uppercase tracking-[0.16em]">Records</p>
                    </div>
                    <p className="mt-3 text-2xl font-bold text-slate-900">{audit.total_candidates}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <div className="flex items-center gap-2 text-slate-500">
                      <ShieldAlert className="h-4 w-4" />
                      <p className="text-xs font-semibold uppercase tracking-[0.16em]">Flagged</p>
                    </div>
                    <p className="mt-3 text-2xl font-bold text-slate-900">{audit.flagged_candidates || 0}</p>
                  </div>
                </div>

                <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Suggested first step</p>
                  <p className="mt-2 text-sm font-medium text-slate-800">{scenarioActions[domain] || "Open audit review"}</p>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  <Link
                    to={`/candidates/${audit.id}`}
                    className="inline-flex items-center justify-center gap-2 rounded-2xl bg-navy px-4 py-3 text-sm font-semibold text-white transition hover:bg-navy-light"
                  >
                    Open candidates
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                  <div className="grid gap-3 sm:grid-cols-2 sm:col-span-1">
                    <Link
                      to={`/mitigate/${audit.id}`}
                      className="inline-flex items-center justify-center rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-amber hover:text-amber-dark"
                    >
                      Mitigation
                    </Link>
                    <Link
                      to={`/governance/${audit.id}`}
                      className="inline-flex items-center justify-center rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-amber hover:text-amber-dark"
                    >
                      Governance
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

export default DemoWorkspace;
