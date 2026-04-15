import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

function MetricComparisonTable({ data }) {
  const chartData = [
    {
      metric: "Disparate Impact",
      original: data.original.disparate_impact,
      reweighing: data.after_reweighing.disparate_impact,
      equalizedOdds: data.after_equalized_odds.disparate_impact,
      prejudiceRemover: data.after_prejudice_remover.disparate_impact
    },
    {
      metric: "Stat Parity Diff",
      original: data.original.stat_parity_diff,
      reweighing: data.after_reweighing.stat_parity_diff,
      equalizedOdds: data.after_equalized_odds.stat_parity_diff,
      prejudiceRemover: data.after_prejudice_remover.stat_parity_diff
    },
    {
      metric: "Equal Opp Diff",
      original: data.original.equal_opp_diff,
      reweighing: data.after_reweighing.equal_opp_diff,
      equalizedOdds: data.after_equalized_odds.equal_opp_diff,
      prejudiceRemover: data.after_prejudice_remover.equal_opp_diff
    },
    {
      metric: "Avg Odds Diff",
      original: data.original.avg_odds_diff,
      reweighing: data.after_reweighing.avg_odds_diff,
      equalizedOdds: data.after_equalized_odds.avg_odds_diff,
      prejudiceRemover: data.after_prejudice_remover.avg_odds_diff
    }
  ];

  return (
    <div className="section-card">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">
            Mitigation Comparison
          </p>
          <h3 className="mt-2 text-2xl font-bold text-slate-900">Before and after fairness metrics</h3>
        </div>
        <div className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-medium text-slate-600">
          80% rule reference line (applies to Disparate Impact)
        </div>
      </div>

      <div className="mt-8 h-[420px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 18, left: 8, bottom: 24 }}>
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
            <XAxis dataKey="metric" tick={{ fill: "#334155", fontSize: 12 }} />
            <YAxis tick={{ fill: "#475569", fontSize: 12 }} />
            <Tooltip />
            <Legend />
            <ReferenceLine
              y={0.8}
              stroke="#b45309"
              strokeDasharray="6 6"
              label={{ value: "80% Rule", fill: "#b45309", position: "insideTopRight", fontSize: 11 }}
            />
            <Bar dataKey="original" name="Original Baseline" fill="#1e3a8a" radius={[10, 10, 0, 0]} isAnimationActive />
            <Bar
              dataKey="reweighing"
              name="After Reweighing"
              fill="#0284c7"
              radius={[10, 10, 0, 0]}
              isAnimationActive
            />
            <Bar
              dataKey="equalizedOdds"
              name="After Equalized Odds"
              fill="#7c3aed"
              radius={[10, 10, 0, 0]}
              isAnimationActive
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-4">
        {chartData.map((row) => (
          <div key={row.metric} className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm font-semibold text-slate-800">{row.metric}</p>
            <p className="mt-3 text-xs uppercase tracking-[0.18em] text-slate-400">Prejudice Remover</p>
            <p className="mt-2 text-2xl font-bold text-navy">{Number(row.prejudiceRemover).toFixed(4)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default MetricComparisonTable;
