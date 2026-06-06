import { Bot, LoaderCircle, ShieldAlert, ShieldCheck, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getAudit, listAudits, runDeepInspection, runGovernanceAuditor } from "../api/fairlensApi";
import GeminiSummaryCard from "../components/GeminiSummaryCard";
import Spinner from "../components/Spinner";

const fairnessDefinitions = [
  {
    label: "Disparate Impact Ratio",
    hint: "A score below 0.8 means a group is selected at under 80% of the highest-rate group."
  },
  {
    label: "Statistical Parity Difference",
    hint: "Difference between selection rates. Values near 0 indicate parity."
  },
  {
    label: "Equal Opportunity Difference",
    hint: "Gap in true-positive rates between protected groups. Values near 0 are better."
  },
  {
    label: "Average Odds Difference",
    hint: "Average of TPR and FPR gaps across groups. Values near 0 indicate lower bias."
  }
];

function verdictFromSignals(agentDecision, deepInspection) {
  const recommendation = agentDecision?.recommendation?.toLowerCase() || "";
  const topProxyRisk = Number(deepInspection?.proxy_findings?.[0]?.risk_score || 0);
  if (topProxyRisk >= 0.2 || recommendation.includes("block") || recommendation.includes("high risk")) {
    return {
      label: "FAIL",
      icon: ShieldAlert,
      tone: "border-rose-300 bg-rose-50 text-rose-800",
      summary: "Critical bias detected. Do not deploy until mitigated."
    };
  }
  if (
    recommendation.includes("recommend") ||
    recommendation.includes("below") ||
    recommendation.includes("review") ||
    topProxyRisk >= 0.08
  ) {
    return {
      label: "FLAG",
      icon: TriangleAlert,
      tone: "border-amber-300 bg-amber-50 text-amber-800",
      summary: "Bias patterns detected. Human review required before production use."
    };
  }
  return {
    label: "PASS",
    icon: ShieldCheck,
    tone: "border-emerald-300 bg-emerald-50 text-emerald-800",
    summary: "No critical bias detected. Safe for monitored rollout."
  };
}

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

function Governance() {
  const { auditId } = useParams();
  const navigate = useNavigate();
  const [audits, setAudits] = useState([]);
  const [selectedAuditId, setSelectedAuditId] = useState(auditId || "");
  const [audit, setAudit] = useState(null);
  const [loadingAudits, setLoadingAudits] = useState(true);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [running, setRunning] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [agentDecision, setAgentDecision] = useState(null);
  const [deepInspection, setDeepInspection] = useState(null);

  const fetchAudits = async () => {
    setLoadingAudits(true);
    setLoadError("");
    try {
      const data = await listAudits({ silent: true });
      setAudits(data);
      const nextAuditId = auditId || data?.[0]?.id || "";
      setSelectedAuditId(nextAuditId);
    } catch (error) {
      setAudits([]);
      setLoadError(extractErrorMessage(error, "Could not reach backend services. Please retry."));
    } finally {
      setLoadingAudits(false);
    }
  };

  useEffect(() => {
    fetchAudits();
  }, [auditId]);

  useEffect(() => {
    if (!selectedAuditId) {
      setAudit(null);
      return;
    }
    const fetchAudit = async () => {
      setLoadingAudit(true);
      try {
        const data = await getAudit(selectedAuditId, { silent: true });
        setAudit(data);
      } catch (error) {
        setAudit(null);
      } finally {
        setLoadingAudit(false);
      }
    };
    fetchAudit();
  }, [selectedAuditId]);

  const runGovernance = async () => {
    if (!selectedAuditId) {
      return;
    }
    setRunning(true);
    try {
      const [agent, inspection] = await Promise.all([
        runGovernanceAuditor(selectedAuditId),
        runDeepInspection(selectedAuditId)
      ]);
      setAgentDecision(agent);
      setDeepInspection(inspection);
    } finally {
      setRunning(false);
    }
  };

  useEffect(() => {
    if (audit && !agentDecision && !running) {
      runGovernance();
    }
  }, [audit, agentDecision, running]);

  const verdict = useMemo(
    () => verdictFromSignals(agentDecision, deepInspection),
    [agentDecision, deepInspection]
  );

  if (loadingAudits) {
    return (
      <div className="section-card flex min-h-[320px] items-center justify-center">
        <Spinner className="h-8 w-8 text-navy" />
      </div>
    );
  }

  if (!audits.length) {
    return (
      <div className="space-y-4">
        {loadError && (
          <div className="section-card border border-rose-200 bg-rose-50/70">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.14em] text-rose-700">Connection issue</p>
                <p className="mt-2 text-sm leading-7 text-rose-900">{loadError}</p>
              </div>
              <button
                type="button"
                onClick={fetchAudits}
                className="inline-flex w-fit items-center rounded-xl border border-rose-300 bg-white px-4 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-100"
              >
                Retry loading audits
              </button>
            </div>
          </div>
        )}
        <div className="section-card text-center">
          <h2 className="text-2xl font-bold text-slate-900">No audits available</h2>
          <p className="mt-3 text-sm text-slate-600">Upload a dataset first, then run governance analysis.</p>
        </div>
      </div>
    );
  }

  const VerdictIcon = verdict.icon;

  return (
    <div className="space-y-6">
      {loadError && (
        <div className="section-card border border-amber-200 bg-amber-50/70">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <p className="text-sm text-amber-900">
              Backend refresh is partially unavailable. Showing the latest available governance context.
            </p>
            <button
              type="button"
              onClick={fetchAudits}
              className="inline-flex w-fit items-center rounded-xl border border-amber-300 bg-white px-4 py-2 text-sm font-semibold text-amber-800 transition hover:bg-amber-100"
            >
              Retry refresh
            </button>
          </div>
        </div>
      )}
      <section className="section-card border border-slate-200 bg-white">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Governance Center</p>
            <h1 className="mt-2 text-3xl font-extrabold text-slate-900">Plain-language fairness verdicts</h1>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              Surface LangGraph recommendations, causal proxy findings, and memory history without reading API logs.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={selectedAuditId}
              onChange={(event) => {
                const nextId = event.target.value;
                setSelectedAuditId(nextId);
                setAgentDecision(null);
                setDeepInspection(null);
                navigate(`/governance/${nextId}`);
              }}
              className="min-w-[260px] rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
            >
              {audits.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.dataset_name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={runGovernance}
              disabled={running || !selectedAuditId}
              className="inline-flex items-center gap-2 rounded-2xl bg-navy px-5 py-3 text-sm font-semibold text-white transition hover:bg-navy-light disabled:cursor-not-allowed disabled:opacity-70"
            >
              {running ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
              {running ? "Running..." : "Run Governance Analysis"}
            </button>
          </div>
        </div>
      </section>

      {loadingAudit ? (
        <div className="section-card flex min-h-[220px] items-center justify-center">
          <Spinner className="h-7 w-7 text-navy" />
        </div>
      ) : running || !agentDecision ? (
        <div className="section-card flex min-h-[300px] flex-col items-center justify-center text-center">
          <Spinner className="h-8 w-8 text-navy" />
          <h2 className="mt-5 text-2xl font-bold text-slate-900">Governance Analysis Running...</h2>
          <div className="mt-4 space-y-2 text-sm text-slate-600 text-left">
            <p className="animate-pulse">1. Analyzing historical audits...</p>
            <p className="animate-pulse" style={{ animationDelay: "1s" }}>2. Evaluating policy compliance...</p>
            <p className="animate-pulse" style={{ animationDelay: "2s" }}>3. Generating compliance matrix...</p>
          </div>
        </div>
      ) : (
        <>
          <GeminiSummaryCard auditId={selectedAuditId} />
          <section className={`section-card border ${verdict.tone}`}>
          <div className="flex items-start gap-4">
            <div className="rounded-2xl bg-white/80 p-3">
              <VerdictIcon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.16em]">Governance Verdict: {verdict.label}</p>
              <h3 className="mt-2 text-2xl font-bold text-slate-900">{verdict.summary}</h3>
              <p className="mt-3 text-sm leading-7 text-slate-700">
                {agentDecision?.recommendation ||
                  "Run analysis to generate a policy-aware recommendation."}
              </p>
              {audit && (
                <p className="mt-3 text-xs uppercase tracking-[0.14em] text-slate-600">
                  Fairness score: {Math.round(audit.fairness_score)} / 100
                </p>
              )}
            </div>
          </div>
        </section>
        </>
      )}

      <section className="section-card border border-slate-200 bg-white">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Proxy Risk Panel</p>
        <h3 className="mt-2 text-2xl font-bold text-slate-900">Causal proxy signals and path view</h3>
        {!deepInspection ? (
          <p className="mt-4 text-sm text-slate-600">Run governance analysis to populate proxy findings.</p>
        ) : (
          <>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {deepInspection.proxy_findings.slice(0, 6).map((finding) => (
                <div key={finding.feature} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">{finding.feature}</p>
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${
                        finding.is_proxy ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"
                      }`}
                    >
                      {finding.is_proxy ? "Flagged Proxy" : "Monitor"}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-600">
                    corr={Number(finding.proxy_strength).toFixed(3)} • effect={Number(finding.treatment_effect).toFixed(3)}
                    {" • "}
                    risk={Number(finding.risk_score).toFixed(3)}
                  </p>
                  <p className="mt-2 text-sm text-slate-700">{finding.explanation}</p>
                </div>
              ))}
            </div>
            <div className="mt-5 rounded-2xl border border-indigo-200 bg-indigo-50 p-4">
              <p className="text-sm font-semibold text-indigo-700">DoWhy Path View</p>
              <p className="mt-2 text-sm leading-7 text-slate-700">
                {deepInspection.dag_edges.length
                  ? deepInspection.dag_edges.map((edge) => `${edge.source} → ${edge.target}`).join("  |  ")
                  : "No strong proxy edges were detected in this run."}
              </p>
            </div>
          </>
        )}
      </section>

      <section className="section-card border border-slate-200 bg-white">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Memory Timeline</p>
        <h3 className="mt-2 text-2xl font-bold text-slate-900">Past governance context from LangGraph memory</h3>
        {!agentDecision?.recalled_memories?.length ? (
          <p className="mt-4 text-sm text-slate-600">No memory snapshots yet. Run the governance agent first.</p>
        ) : (
          <div className="mt-5 space-y-3">
            {agentDecision.recalled_memories.map((memory, index) => {
              const text = memory.memory_text || "";
              const parts = text.split('|').map(s => s.trim());
              let stage = memory.stage?.toUpperCase() || 'UNKNOWN';
              let dataset = 'unknown_dataset';
              let fairness = '--';
              let di = '--';
              let recommendation = 'Audit recorded for governance tracking.';

              parts.forEach(part => {
                if (part.startsWith('stage=')) stage = part.substring(6).toUpperCase();
                if (part.startsWith('dataset=')) dataset = part.substring(8);
                if (part.startsWith('recommendation=')) recommendation = part.substring(15);
              });

              const fairnessMatch = text.match(/fairness=([\d.]+)/i);
              if (fairnessMatch) fairness = fairnessMatch[1];

              const diMatch = text.match(/DI=([\d.-]+)/i);
              if (diMatch) di = diMatch[1];

              return (
                <div key={`${memory.stage}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center gap-3">
                    <span className="inline-flex rounded-full bg-navy px-2 py-1 text-xs font-semibold text-white">
                      {stage}
                    </span>
                    <span className="text-sm font-semibold text-slate-900">{dataset}</span>
                  </div>
                  <p className="mt-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                    Fairness: {fairness}/100 • DI: {di}
                  </p>
                  <p className="mt-3 text-sm leading-7 text-slate-700">{recommendation}</p>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="section-card border border-slate-200 bg-white">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Fairness Glossary</p>
        <h3 className="mt-2 text-2xl font-bold text-slate-900">Hover definitions for accessibility</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {fairnessDefinitions.map((item) => (
            <div
              key={item.label}
              title={item.hint}
              className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700"
            >
              <span className="font-semibold text-slate-900">{item.label}:</span> {item.hint}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export default Governance;
