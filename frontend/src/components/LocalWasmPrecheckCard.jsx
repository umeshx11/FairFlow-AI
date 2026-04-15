function StatusPill({ pass, label }) {
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.15em] ${
        pass ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
      }`}
    >
      {label}
    </span>
  );
}

function MetricTile({ label, value, threshold, pass }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-slate-800">{label}</p>
        <StatusPill pass={pass} label={pass ? "Pass" : "Flag"} />
      </div>
      <p className="mt-3 text-2xl font-bold text-slate-900">{value}</p>
      <p className="mt-1 text-xs uppercase tracking-[0.15em] text-slate-500">{threshold}</p>
    </div>
  );
}

function LocalWasmPrecheckCard({ result, proxyColumn }) {
  if (!result) {
    return null;
  }

  const diPass = result.disparateImpact > 0.8;
  const tprPass = Math.abs(result.tprGap) < 0.1;
  const fprPass = Math.abs(result.fprGap) < 0.1;

  return (
    <section className="section-card border border-blue-100 bg-[linear-gradient(135deg,#eff6ff_0%,#ffffff_60%,#f8fafc_100%)]">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-700">Local WASM Precheck</p>
          <h3 className="mt-2 text-2xl font-bold text-slate-900">
            Client-side fairness pass ({result.engine.toUpperCase()} engine)
          </h3>
          <p className="mt-2 text-sm text-slate-600">
            Processed {Math.round(result.sampleCount)} rows with zero data egress before upload.
          </p>
        </div>
        <div className="rounded-2xl border border-blue-100 bg-white px-4 py-3 text-sm text-slate-700">
          Proxy feature: <span className="font-semibold">{proxyColumn.replaceAll("_", " ")}</span>
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricTile
          label="Disparate Impact"
          value={result.disparateImpact.toFixed(4)}
          threshold="> 0.80"
          pass={diPass}
        />
        <MetricTile
          label="Equalized Odds"
          value={result.equalizedOdds.toFixed(4)}
          threshold="Lower is better"
          pass={tprPass && fprPass}
        />
        <MetricTile
          label="TPR Gap"
          value={result.tprGap.toFixed(4)}
          threshold="|x| < 0.10"
          pass={tprPass}
        />
        <MetricTile
          label="FPR Gap"
          value={result.fprGap.toFixed(4)}
          threshold="|x| < 0.10"
          pass={fprPass}
        />
      </div>

      <div className="mt-5 rounded-2xl border border-slate-200 bg-white px-4 py-4 text-sm text-slate-700">
        Fairness score: <span className="font-semibold">{Math.round(result.fairnessScore)} / 100</span> • Proxy
        correlation score: <span className="font-semibold">{result.proxyScore.toFixed(4)}</span>
      </div>
    </section>
  );
}

export default LocalWasmPrecheckCard;

