import { Dialog, Transition } from "@headlessui/react";
import {
  AlertTriangle,
  ArrowRightLeft,
  BadgeCheck,
  Bot,
  Download,
  FileText,
  LoaderCircle,
  Sparkles,
  TrendingUp,
  XCircle
} from "lucide-react";
import { Fragment, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { useParams } from "react-router-dom";

import {
  LAST_AUDIT_STORAGE_KEY,
  downloadReport,
  getAudit,
  mitigateAudit,
  runDeepInspection,
  runGovernanceAuditor,
  runSyntheticPatch
} from "../api/fairlensApi";
import MetricComparisonTable from "../components/MetricComparisonTable";
import Spinner from "../components/Spinner";

const metricLabels = {
  disparate_impact: "Disparate Impact",
  stat_parity_diff: "Statistical Parity Difference",
  equal_opp_diff: "Equal Opportunity Difference",
  avg_odds_diff: "Average Odds Difference"
};

const metricThresholds = {
  disparate_impact: "> 0.80",
  stat_parity_diff: "|x| < 0.10",
  equal_opp_diff: "|x| < 0.10",
  avg_odds_diff: "|x| < 0.10"
};

function buildMitigationSummary(result) {
  if (!result) {
    return null;
  }

  const passFlags = result.after_equalized_odds?.pass_flags || {};
  const passCount = Object.values(passFlags).filter(Boolean).length;

  if (passCount === 4) {
    return {
      badge: "Audit Pass",
      badgeClass: "border-emerald-200 bg-emerald-50 text-emerald-700",
      title: "Mitigation brought the audit into the target range.",
      description:
        "All fairness checks now pass after the final mitigation stage, so this audit is in much stronger shape for rollout review and stakeholder sign-off.",
      tone: "border-emerald-200 bg-emerald-50/60"
    };
  }

  if (passCount >= 2) {
    return {
      badge: "Improved, Still Open",
      badgeClass: "border-amber-200 bg-amber-50 text-amber-800",
      title: "Mitigation helped, but there are still open fairness gaps.",
      description:
        "Several checks moved into range, but the remaining failing metrics should be reviewed before the model is treated as fully clean.",
      tone: "border-amber-200 bg-amber-50/60"
    };
  }

  return {
    badge: "Needs More Work",
    badgeClass: "border-rose-200 bg-rose-50 text-rose-700",
    title: "Mitigation reduced risk only slightly.",
    description:
      "Most fairness checks are still failing after mitigation, so the ranking model should stay under review before production use.",
    tone: "border-rose-200 bg-rose-50/60"
  };
}

function formatMetricValue(value) {
  return Number(value ?? 0).toFixed(4);
}

function MetricProgress({ label, beforeValue, afterValue }) {
  const normalisedAfter = Math.min(100, Math.round(Math.abs(afterValue) * 100));
  const delta = Number(afterValue) - Number(beforeValue);

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm font-semibold text-slate-800">{label}</p>
        <p className="text-sm font-medium text-slate-500">
          {Number(beforeValue).toFixed(2)} → {Number(afterValue).toFixed(2)}
        </p>
      </div>
      <div className="mt-4 h-3 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-[linear-gradient(90deg,#f59e0b_0%,#16a34a_100%)] transition-all duration-[1500ms]"
          style={{ width: `${normalisedAfter}%` }}
        />
      </div>
      <p className="mt-3 text-sm font-medium text-slate-500">
        {delta >= 0 ? "+" : ""}
        {delta.toFixed(2)} change after mitigation
      </p>
    </div>
  );
}

function Mitigate() {
  const { auditId } = useParams();
  const [audit, setAudit] = useState(null);
  const [result, setResult] = useState(null);
  const [loadingAudit, setLoadingAudit] = useState(true);
  const [running, setRunning] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [agentDecision, setAgentDecision] = useState(null);
  const [loadingAgentDecision, setLoadingAgentDecision] = useState(false);
  const [syntheticResult, setSyntheticResult] = useState(null);
  const [runningSynthetic, setRunningSynthetic] = useState(false);
  const [deepInspection, setDeepInspection] = useState(null);
  const [loadingDeepInspection, setLoadingDeepInspection] = useState(false);

  useEffect(() => {
    if (auditId) {
      localStorage.setItem(LAST_AUDIT_STORAGE_KEY, auditId);
    }
  }, [auditId]);

  useEffect(() => {
    const fetchAudit = async () => {
      setLoadingAudit(true);
      try {
        const data = await getAudit(auditId);
        setAudit(data);
      } catch (error) {
        setAudit(null);
      } finally {
        setLoadingAudit(false);
      }
    };

    fetchAudit();
  }, [auditId]);

  const handleRunMitigation = async () => {
    setRunning(true);
    setAgentDecision(null);
    try {
      const response = await mitigateAudit(auditId);
      setResult(response);
      setLoadingAgentDecision(true);
      setLoadingDeepInspection(true);
      try {
        const recommendation = await runGovernanceAuditor(auditId);
        setAgentDecision(recommendation);
      } catch (error) {
        setAgentDecision(null);
      } finally {
        setLoadingAgentDecision(false);
      }
      try {
        const inspection = await runDeepInspection(auditId);
        setDeepInspection(inspection);
      } catch (error) {
        setDeepInspection(null);
      } finally {
        setLoadingDeepInspection(false);
      }
    } catch (error) {
      setLoadingAgentDecision(false);
      return;
    } finally {
      setRunning(false);
    }
  };

  const handleDownloadReport = async () => {
    try {
      const blob = await downloadReport(auditId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${audit?.dataset_name?.replace(".csv", "") || "fairflow"}_report.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      return;
    }
  };

  const handleRunSyntheticPatch = async () => {
    setRunningSynthetic(true);
    try {
      const response = await runSyntheticPatch(auditId, "gender");
      setSyntheticResult(response);
      toast.success(
        response.enabled
          ? `Synthetic patch generated ${response.generated_rows} profiles.`
          : response.reason || "Synthetic patch did not generate rows."
      );
    } catch (error) {
      return;
    } finally {
      setRunningSynthetic(false);
    }
  };

  const fairnessLiftPoints = useMemo(() => {
    if (!result) {
      return 0;
    }
    return Number((result.fairness_score_after - result.fairness_score_before).toFixed(1));
  }, [result]);

  const mitigationSummary = useMemo(() => buildMitigationSummary(result), [result]);

  const passingMetrics = useMemo(
    () =>
      Object.entries(result?.after_equalized_odds?.pass_flags || {})
        .filter(([, passed]) => passed)
        .map(([key]) => ({
          key,
          label: metricLabels[key],
          value: result.after_equalized_odds[key],
          threshold: metricThresholds[key]
        })),
    [result]
  );

  const failingMetrics = useMemo(
    () =>
      Object.entries(result?.after_equalized_odds?.pass_flags || {})
        .filter(([, passed]) => !passed)
        .map(([key]) => ({
          key,
          label: metricLabels[key],
          value: result.after_equalized_odds[key],
          threshold: metricThresholds[key]
        })),
    [result]
  );

  const summaryHeadline = useMemo(() => {
    if (!result) {
      return "";
    }
    if (fairnessLiftPoints > 0) {
      return `Mitigation improved fairness score by ${Math.abs(fairnessLiftPoints)} points`;
    }
    if (fairnessLiftPoints < 0) {
      return `Mitigation reduced fairness score by ${Math.abs(fairnessLiftPoints)} points`;
    }
    return "Mitigation kept the fairness score level";
  }, [fairnessLiftPoints, result]);

  if (loadingAudit) {
    return (
      <div className="section-card flex min-h-[320px] items-center justify-center">
        <Spinner className="h-8 w-8 text-navy" />
      </div>
    );
  }

  if (!audit) {
    return (
      <div className="section-card flex min-h-[360px] flex-col items-center justify-center text-center">
        <FileText className="h-10 w-10 text-slate-300" />
        <h2 className="mt-5 text-3xl font-bold text-slate-900">No audit found</h2>
        <p className="mt-3 max-w-xl text-sm leading-7 text-slate-500">
          Open this page from an existing audit or upload a new dataset to run mitigation analysis.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="section-card overflow-hidden bg-[linear-gradient(135deg,#0f172a_0%,#1e293b_50%,#f59e0b_120%)] text-white">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-light">Mitigation Center</p>
            <h1 className="mt-4 text-4xl font-extrabold">Compare mitigation strategies before rollout</h1>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-300">
              Run reweighing, prejudice remover, and equalized odds post-processing against{" "}
              <span className="font-semibold text-white">{audit.dataset_name}</span> to understand
              how fairness metrics shift before rankings are refreshed.
            </p>
          </div>
          <button
            type="button"
            onClick={handleRunMitigation}
            disabled={running}
            className="inline-flex items-center justify-center gap-3 rounded-3xl bg-white px-6 py-4 text-sm font-semibold text-navy transition hover:bg-amber/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-70"
          >
            {running ? <LoaderCircle className="h-5 w-5 animate-spin" /> : <Sparkles className="h-5 w-5" />}
            {running ? "Applying 3 mitigation strategies..." : "Run Mitigation Analysis"}
          </button>
        </div>
      </div>

      {!result && (
        <div className="section-card text-center">
          <h2 className="text-2xl font-bold text-slate-900">Mitigation analysis has not been run yet</h2>
          <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-slate-500">
            Start the mitigation workflow to compute before-and-after fairness metrics, update
            candidate ranking decisions, and enable PDF report export.
          </p>
        </div>
      )}

      {result && mitigationSummary && (
        <>
          <div className="section-card border border-indigo-200 bg-indigo-50/60">
            <div className="flex items-start gap-4">
              <div className="rounded-2xl bg-indigo-100 p-3 text-indigo-700">
                <Bot className="h-5 w-5" />
              </div>
              <div className="space-y-2">
                <p className="text-sm font-semibold uppercase tracking-[0.18em] text-indigo-700">
                  Ethos Agent Recommendation
                </p>
                {loadingAgentDecision ? (
                  <p className="text-sm text-slate-600">Analyzing historical audits and policy memories...</p>
                ) : (
                  <>
                    <p className="text-base font-semibold text-slate-900">
                      {agentDecision?.recommendation ||
                        "Disparate Impact is below the 0.8 threshold. Recommend applying Equalized Odds post-processing and reviewing changed outcomes."}
                    </p>
                    {agentDecision?.rationale && (
                      <p className="text-sm leading-7 text-slate-600">{agentDecision.rationale}</p>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>

          {syntheticResult && (
            <div className="section-card border border-emerald-200 bg-emerald-50/70">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-emerald-700">
                Debias Now Synthetic Patch
              </p>
              <h3 className="mt-2 text-2xl font-bold text-slate-900">
                {syntheticResult.enabled
                  ? `${syntheticResult.generated_rows} counterfactual profiles generated`
                  : "Synthetic patch completed without new rows"}
              </h3>
              <p className="mt-3 text-sm leading-7 text-slate-700">
                Engine: <span className="font-semibold">{syntheticResult.engine}</span> • Fairness
                lift: <span className="font-semibold">{syntheticResult.fairness_lift}</span> points
              </p>
              {syntheticResult.reason && (
                <p className="mt-2 text-sm text-slate-600">{syntheticResult.reason}</p>
              )}
            </div>
          )}

          <div className="section-card border border-slate-200 bg-white">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">
              Concept Sensitivity (TCAV)
            </p>
            <h3 className="mt-2 text-2xl font-bold text-slate-900">Glass Box concept influence view</h3>
            {loadingDeepInspection ? (
              <p className="mt-3 text-sm text-slate-600">Running causal + TCAV deep inspection...</p>
            ) : deepInspection?.tcav_concepts?.length ? (
              <>
                <div className="mt-5 space-y-4">
                  {deepInspection.tcav_concepts.slice(0, 5).map((concept) => {
                    const width = Math.max(8, Math.min(100, Math.round(Math.abs(concept.sensitivity) * 100)));
                    return (
                      <div key={concept.concept}>
                        <div className="flex items-center justify-between gap-3 text-sm">
                          <p className="font-semibold text-slate-800">{concept.concept}</p>
                          <p className="text-slate-500">
                            tcav={Number(concept.tcav_score).toFixed(2)} • sens=
                            {Number(concept.sensitivity).toFixed(2)}
                          </p>
                        </div>
                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full bg-[linear-gradient(90deg,#0f172a_0%,#f59e0b_100%)]"
                            style={{ width: `${width}%` }}
                          />
                        </div>
                        <p className="mt-1 text-xs text-slate-500">{concept.summary}</p>
                      </div>
                    );
                  })}
                </div>
                {deepInspection?.proxy_findings?.[0] && (
                  <p className="mt-5 rounded-2xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-slate-700">
                    Top causal proxy path:{" "}
                    <span className="font-semibold">{deepInspection.proxy_findings[0].feature}</span> (
                    risk={Number(deepInspection.proxy_findings[0].risk_score).toFixed(3)})
                  </p>
                )}
              </>
            ) : (
              <p className="mt-3 text-sm text-slate-600">
                Deep inspection data is not available for this run yet.
              </p>
            )}
          </div>

          <MetricComparisonTable data={result} />

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {Object.entries(metricLabels).map(([key, label]) => (
              <MetricProgress
                key={key}
                label={label}
                beforeValue={result.original[key]}
                afterValue={result.after_equalized_odds[key]}
              />
            ))}
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
            <div className={`section-card border ${mitigationSummary.tone}`}>
              <div className="flex flex-col gap-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span
                    className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${mitigationSummary.badgeClass}`}
                  >
                    {mitigationSummary.badge}
                  </span>
                  <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                    <TrendingUp className="h-3.5 w-3.5 text-amber-dark" />
                    Fairness score {result.fairness_score_before}% → {result.fairness_score_after}%
                  </span>
                  <span className="inline-flex items-center rounded-full bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                    {passingMetrics.length} of {Object.keys(metricLabels).length} checks in range
                  </span>
                </div>

                <div>
                  <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Mitigation Readout</p>
                  <h3 className="mt-2 text-3xl font-bold text-slate-900">{mitigationSummary.title}</h3>
                  <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
                    {mitigationSummary.description}
                  </p>
                </div>
              </div>

              <div className="mt-6 grid gap-4 lg:grid-cols-2">
                <div className="rounded-3xl border border-emerald-200 bg-white p-5">
                  <div className="flex items-center gap-3">
                    <BadgeCheck className="h-5 w-5 text-emerald-600" />
                    <p className="text-sm font-semibold uppercase tracking-[0.16em] text-emerald-700">
                      Passing Checks
                    </p>
                  </div>
                  <div className="mt-4 space-y-3">
                    {passingMetrics.length ? (
                      passingMetrics.map((metric) => (
                        <div key={metric.key} className="rounded-2xl bg-emerald-50 px-4 py-3">
                          <p className="text-sm font-semibold text-slate-900">{metric.label}</p>
                          <p className="mt-1 text-sm text-slate-600">
                            {formatMetricValue(metric.value)} • threshold {metric.threshold}
                          </p>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">No fairness checks are passing yet.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-3xl border border-rose-200 bg-white p-5">
                  <div className="flex items-center gap-3">
                    <XCircle className="h-5 w-5 text-rose-600" />
                    <p className="text-sm font-semibold uppercase tracking-[0.16em] text-rose-700">
                      Remaining Gaps
                    </p>
                  </div>
                  <div className="mt-4 space-y-3">
                    {failingMetrics.length ? (
                      failingMetrics.map((metric) => (
                        <div key={metric.key} className="rounded-2xl bg-rose-50 px-4 py-3">
                          <p className="text-sm font-semibold text-slate-900">{metric.label}</p>
                          <p className="mt-1 text-sm text-slate-600">
                            {formatMetricValue(metric.value)} • threshold {metric.threshold}
                          </p>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">No remaining fairness gaps in the final metric set.</p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="section-card">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Decision Summary</p>
                <h3 className="mt-2 text-2xl font-bold text-slate-900">{summaryHeadline}</h3>
                <p className="mt-3 text-sm leading-7 text-slate-600">
                  {result.mitigated_candidates > 0
                    ? `Model recommendations updated for ${result.mitigated_candidates} records.`
                    : "No recommendation flips were required for this run."}{" "}
                  You can now export a stakeholder-ready PDF or confirm the recalculated rankings.
                </p>
              </div>

              <div
                className={`mt-6 rounded-3xl border p-4 ${
                  failingMetrics.length
                    ? "border-amber-200 bg-amber-50"
                    : "border-emerald-200 bg-emerald-50"
                }`}
              >
                <div className="flex items-start gap-3">
                  {failingMetrics.length ? (
                    <AlertTriangle className="mt-0.5 h-5 w-5 text-amber-dark" />
                  ) : (
                    <BadgeCheck className="mt-0.5 h-5 w-5 text-emerald-600" />
                  )}
                  <p className="text-sm leading-7 text-slate-600">
                    {failingMetrics.length
                      ? "The strongest remaining concerns are the metrics still outside the accepted range after equalized odds. Review those before calling the audit clean."
                      : "The final metric set is fully inside the target range, so this audit is ready for a cleaner stakeholder handoff."}
                  </p>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={handleRunSyntheticPatch}
                  disabled={runningSynthetic}
                  className="inline-flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-800 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {runningSynthetic ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  {runningSynthetic ? "Generating synthetic profiles..." : "Debias Now (Synthetic Patch)"}
                </button>
                <button
                  type="button"
                  onClick={handleDownloadReport}
                  className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-amber hover:text-amber-dark"
                >
                  <Download className="h-4 w-4" />
                  Download PDF Report
                </button>
                <button
                  type="button"
                  onClick={() => setShowModal(true)}
                  className="inline-flex items-center gap-2 rounded-2xl bg-navy px-4 py-3 text-sm font-semibold text-white transition hover:bg-navy-light"
                >
                  <ArrowRightLeft className="h-4 w-4" />
                  Apply to Rankings
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      <Transition.Root show={showModal} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={setShowModal}>
          <Transition.Child
            as={Fragment}
            enter="transition-opacity duration-200"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="transition-opacity duration-150"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm" />
          </Transition.Child>

          <div className="fixed inset-0 flex items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="transform transition duration-200"
              enterFrom="scale-95 opacity-0"
              enterTo="scale-100 opacity-100"
              leave="transform transition duration-150"
              leaveFrom="scale-100 opacity-100"
              leaveTo="scale-95 opacity-0"
            >
              <Dialog.Panel className="w-full max-w-lg rounded-[32px] bg-white p-8 shadow-2xl">
                <Dialog.Title className="text-2xl font-bold text-slate-900">
                  Recalculated decisions are ready
                </Dialog.Title>
                <p className="mt-4 text-sm leading-7 text-slate-600">
                  Equalized odds mitigation has already updated the stored mitigated decisions for this
                  audit. Confirming here lets your team proceed with the adjusted rankings confidently.
                </p>
                <div className="mt-8 flex gap-3">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="flex-1 rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700"
                  >
                    Close
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      toast.success("Mitigated rankings confirmed for this audit.");
                      setShowModal(false);
                    }}
                    className="flex-1 rounded-2xl bg-navy px-4 py-3 text-sm font-semibold text-white"
                  >
                    Confirm Rankings
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </Dialog>
      </Transition.Root>
    </div>
  );
}

export default Mitigate;
