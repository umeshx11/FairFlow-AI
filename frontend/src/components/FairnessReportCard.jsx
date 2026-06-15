import { BadgeCheck, Scale, XCircle } from "lucide-react";

const metricConfig = [
  {
    key: "disparate_impact",
    label: "Disparate Impact",
    threshold: "> 0.80",
    isPassing: (value) => Number(value) > 0.8
  },
  {
    key: "stat_parity_diff",
    label: "Statistical Parity Diff",
    threshold: "|x| < 0.10",
    isPassing: (value) => Math.abs(Number(value)) < 0.1
  },
  {
    key: "equal_opp_diff",
    label: "Equal Opportunity Diff",
    threshold: "|x| < 0.10",
    isPassing: (value) => Math.abs(Number(value)) < 0.1
  },
  {
    key: "avg_odds_diff",
    label: "Average Odds Diff",
    threshold: "|x| < 0.10",
    isPassing: (value) => Math.abs(Number(value)) < 0.1
  }
];

function FairnessReportCard({ metrics }) {
  const computedMetrics = metricConfig.map((metric) => {
    const value = Number(metrics?.[metric.key] ?? 0);
    return {
      ...metric,
      value,
      pass: metric.isPassing(value)
    };
  });

  const overallScore = Math.round(
    (computedMetrics.filter((metric) => metric.pass).length / computedMetrics.length) * 100
  );

  return (
    <section className="section-card">
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-amber-dark">
            Fairness Snapshot
          </p>
          <h3 className="mt-2 text-2xl font-bold text-slate-900">Bias metric assessment</h3>
          <p className="mt-2 text-sm text-slate-500">
            WASM precheck score uses browser-side metrics. Full server analysis includes additional dimensions.
          </p>
        </div>
        <div className="inline-flex items-center gap-3 self-start rounded-full border border-slate-200 bg-slate-50 px-4 py-2">
          <Scale className="h-4 w-4 text-amber-dark" />
          <span className="text-sm font-semibold text-slate-700">Overall score: {overallScore}/100</span>
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {computedMetrics.map((metric) => (
          <div
            key={metric.key}
            className={`rounded-3xl border p-5 ${
              metric.pass
                ? "border-emerald-200 bg-emerald-50"
                : "border-red-200 bg-red-50"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-700">{metric.label}</p>
                <p className="mt-3 text-3xl font-bold text-slate-900">{metric.value.toFixed(4)}</p>
              </div>
              {metric.pass ? (
                <BadgeCheck className="h-6 w-6 text-emerald-600" />
              ) : (
                <XCircle className="h-6 w-6 text-red-600" />
              )}
            </div>
            <div className="mt-5 flex items-center justify-between text-sm">
              <span className="font-medium text-slate-600">Threshold</span>
              <span className="rounded-full bg-white/70 px-3 py-1 font-semibold text-slate-700">
                {metric.threshold}
              </span>
            </div>
            <div className="mt-4 inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-white">
              <span className={`rounded-full px-3 py-1 ${metric.pass ? "bg-emerald-600" : "bg-red-600"}`}>
                {metric.pass ? "PASS" : "FAIL"}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default FairnessReportCard;
