import { AlertTriangle, ArrowRight, CircleCheckBig } from "lucide-react";

function DecisionBadge({ label, active }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-4 py-2 text-sm font-semibold ${
        active ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
      }`}
    >
      {label}
    </span>
  );
}

function CounterfactualPanel({ result }) {
  if (!result) {
    return (
      <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-500">
        No counterfactual result is available for this candidate yet.
      </div>
    );
  }

  const confidencePercentage = Math.min(100, Math.round(Number(result.confidence || 0) * 100));

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Counterfactual</p>
          <h3 className="mt-2 text-xl font-bold text-slate-900">Decision parity test (What-if sandbox)</h3>
        </div>
        <CircleCheckBig className="h-6 w-6 text-navy" />
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-4">
        <DecisionBadge
          label={result.original_decision ? "Hired" : "Rejected"}
          active={result.original_decision}
        />
        <ArrowRight className="h-5 w-5 text-slate-400" />
        <DecisionBadge
          label={result.counterfactual_decision ? "Hired" : "Rejected"}
          active={result.counterfactual_decision}
        />
      </div>

      {result.bias_detected && (
        <div className="mt-5 flex items-start gap-3 rounded-3xl border border-amber-200 bg-amber-50 px-4 py-4 text-amber-900">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <p className="text-sm leading-6">
            Bias detected: the outcome flips under a protected-attribute change ({result.changed_attributes.join(", ")}).
          </p>
        </div>
      )}

      <div className="mt-5">
        <div className="mb-2 flex items-center justify-between text-sm font-medium text-slate-600">
          <span>Confidence</span>
          <span>{confidencePercentage}%</span>
        </div>
        <div className="h-3 overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-[linear-gradient(90deg,#f59e0b_0%,#0f172a_100%)] transition-all duration-700"
            style={{ width: `${confidencePercentage}%` }}
          />
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {result.changed_attributes?.length ? (
          result.changed_attributes.map((attribute) => (
            <span
              key={attribute}
              className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.15em] text-slate-700"
            >
              {attribute.replaceAll("_", " ")}
            </span>
          ))
        ) : (
          <span className="text-sm text-slate-500">No protected attributes were changed.</span>
        )}
      </div>
    </div>
  );
}

export default CounterfactualPanel;
