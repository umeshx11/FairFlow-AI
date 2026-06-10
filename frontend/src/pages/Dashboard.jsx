import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { ArrowUpRight, FolderSearch, Gauge, ShieldAlert, ShieldCheck, Trash2, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";

import { LAST_AUDIT_STORAGE_KEY, deleteAudit, listAudits } from "../api/fairlensApi";

const ethnicityColors = ["#2563eb", "#ec4899", "#16a34a", "#f97316"];

const domainBadgeStyles = {
  hiring: "bg-blue-100 text-blue-700",
  lending: "bg-amber-100 text-amber-800",
  healthcare: "bg-teal-100 text-teal-700",
  custom: "bg-slate-200 text-slate-700"
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

function domainLabel(audit) {
  return audit?.domain_config?.display_name || "Hiring";
}

function domainKey(audit) {
  return (audit?.domain_config?.domain || "hiring").toLowerCase();
}

function StatCard({ label, value, icon: Icon, trend, accent }) {
  return (
    <div className="section-card">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">{label}</p>
          <p className="mt-4 text-4xl font-extrabold text-slate-900">{value}</p>
        </div>
        <div className={`rounded-2xl p-3 ${accent}`}>
          <Icon className="h-6 w-6" />
        </div>
      </div>
      <div className="mt-6 inline-flex items-center gap-2 rounded-full bg-slate-50 px-3 py-2 text-sm font-medium text-slate-600">
        <ArrowUpRight className="h-4 w-4 text-emerald-600" />
        {trend}
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="h-40 rounded-3xl bg-white" />
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <div className="h-[380px] rounded-3xl bg-white" />
        <div className="h-[380px] rounded-3xl bg-white" />
      </div>
      <div className="h-[420px] rounded-3xl bg-white" />
    </div>
  );
}

function Dashboard() {
  const [audits, setAudits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [deletingId, setDeletingId] = useState(null);

  const fetchAudits = async () => {
    setLoading(true);
    setLoadError("");
    try {
      const data = await listAudits({ silent: true });
      setAudits(data);
      if (data[0]?.id) {
        localStorage.setItem(LAST_AUDIT_STORAGE_KEY, data[0].id);
      }
    } catch (error) {
      setAudits([]);
      setLoadError(extractErrorMessage(error, "Backend is unavailable. Start API server on port 8000 and retry."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAudits();
  }, []);

  const handleDelete = async (auditId, datasetName) => {
    if (!window.confirm(`Permanently delete "${datasetName}" and all its candidate data? This cannot be undone.`)) return;
    setDeletingId(auditId);
    try {
      await deleteAudit(auditId);
      setAudits((prev) => prev.filter((a) => a.id !== auditId));
    } catch {
      // toast already shown by performRequest
    } finally {
      setDeletingId(null);
    }
  };

  const latestAudit = audits[0];
  const stats = useMemo(() => {
    const totalCandidates = audits.reduce((sum, audit) => sum + audit.total_candidates, 0);
    const biasFlags = audits.reduce((sum, audit) => sum + (audit.flagged_candidates || 0), 0);
    const averageFairness =
      audits.length > 0
        ? Math.round(audits.reduce((sum, audit) => sum + audit.fairness_score, 0) / audits.length)
        : 0;
    const mitigatedAudits = audits.filter((audit) => audit.mitigation_applied).length;
    const scoreTrend =
      audits.length > 1 ? Math.round(audits[0].fairness_score - audits[1].fairness_score) : averageFairness;

    return {
      totalCandidates,
      biasFlags,
      averageFairness,
      mitigatedAudits,
      scoreTrend
    };
  }, [audits]);

  const genderData = useMemo(
    () =>
      Object.entries(latestAudit?.gender_hire_rates || {}).map(([group, rate]) => ({
        group,
        rate: Math.round(rate * 100),
        fill: group === "Male" ? "#2563eb" : "#ec4899"
      })),
    [latestAudit]
  );

  const ethnicityData = useMemo(
    () =>
      Object.entries(latestAudit?.ethnicity_hire_rates || {}).map(([group, rate], index) => ({
        group,
        rate: Math.round(rate * 100),
        fill: ethnicityColors[index % ethnicityColors.length]
      })),
    [latestAudit]
  );

  const trendData = useMemo(
    () =>
      [...audits]
        .slice(0, 5)
        .reverse()
        .map((audit) => ({
          label: new Date(audit.created_at).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric"
          }),
          fairnessScore: Math.round(audit.fairness_score)
        })),
    [audits]
  );

  const heroStats = useMemo(
    () => [
      {
        label: "Latest Dataset",
        value: latestAudit?.dataset_name?.replace(/\.csv$/i, "") || "No dataset yet",
        valueClassName: "text-base leading-6 xl:text-lg break-words",
        title: latestAudit?.dataset_name || "No dataset yet"
      },
      {
        label: "Latest Score",
        value: latestAudit ? `${Math.round(latestAudit.fairness_score)} / 100` : "0 / 100",
        valueClassName: "text-2xl xl:text-3xl leading-tight",
        title: latestAudit ? `${Math.round(latestAudit.fairness_score)} / 100` : "0 / 100"
      },
      {
        label: "Flagged Candidates",
        value: latestAudit?.flagged_candidates ?? 0,
        valueClassName: "text-2xl xl:text-3xl leading-tight",
        title: String(latestAudit?.flagged_candidates ?? 0)
      },
      {
        label: "Mitigation",
        value: latestAudit?.mitigation_applied ? "Applied" : "Pending",
        valueClassName: "text-2xl xl:text-3xl leading-tight",
        title: latestAudit?.mitigation_applied ? "Applied" : "Pending"
      }
    ],
    [latestAudit]
  );

  if (loading) {
    return <LoadingSkeleton />;
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
        <div className="section-card flex min-h-[420px] flex-col items-center justify-center text-center">
          <div className="rounded-full bg-amber/10 p-4 text-amber-dark">
            <FolderSearch className="h-8 w-8" />
          </div>
          <h2 className="mt-6 text-3xl font-bold text-slate-900">No audits yet</h2>
          <p className="mt-3 max-w-xl text-sm leading-7 text-slate-500">
            Upload your first dataset to generate fairness metrics, decision explanations,
            and mitigation recommendations.
          </p>
          <Link
            to="/audit"
            className="mt-8 inline-flex items-center rounded-2xl bg-navy px-5 py-3 text-sm font-semibold text-white transition hover:bg-navy-light"
          >
            Start Your First Audit
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="text-center text-[13px] text-amber-600/90 font-medium">
        83% of companies use AI in decisions. Fewer than 12% audit for bias. FairFlow fixes that.
      </div>
      {loadError && (
        <div className="section-card border border-amber-200 bg-amber-50/70">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <p className="text-sm text-amber-900">
              Some data could not refresh from backend. Showing last available results.
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
      <div className="section-card overflow-hidden bg-[linear-gradient(135deg,#0f172a_0%,#1e293b_55%,#334155_100%)] text-white">
        <div className="grid gap-8 xl:grid-cols-[minmax(0,1.15fr)_minmax(420px,0.85fr)]">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-amber-light">Operations Pulse</p>
            <h1 className="mt-4 text-4xl font-extrabold leading-tight">
              Fairness oversight across hiring, lending, and healthcare in one decision cockpit.
            </h1>
            <p className="mt-5 max-w-2xl text-sm leading-7 text-slate-300">
              Track risk, investigate candidate-level bias signals, and compare mitigation outcomes
              before those rankings reach your recruiting teams.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {heroStats.map((item) => (
              <div
                key={item.label}
                className="min-w-0 rounded-3xl border border-white/10 bg-white/5 p-5 min-h-[132px]"
              >
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{item.label}</p>
                <p className={`mt-4 font-bold text-white ${item.valueClassName}`} title={item.title}>
                  {item.value}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total Candidates"
          value={stats.totalCandidates}
          icon={Users}
          trend={`${audits.length} audits recorded`}
          accent="bg-blue-50 text-blue-700"
        />
        <StatCard
          label="Bias Flags"
          value={stats.biasFlags}
          icon={ShieldAlert}
          trend={`${latestAudit.flagged_candidates} in latest audit`}
          accent="bg-rose-50 text-rose-700"
        />
        <StatCard
          label="Fairness Score"
          value={`${stats.averageFairness}%`}
          icon={Gauge}
          trend={`${stats.scoreTrend >= 0 ? "+" : ""}${stats.scoreTrend}% vs previous`}
          accent="bg-amber-50 text-amber-dark"
        />
        <StatCard
          label="Mitigated Audits"
          value={stats.mitigatedAudits}
          icon={ShieldCheck}
          trend={`${stats.mitigatedAudits}/${audits.length} with action`}
          accent="bg-emerald-50 text-emerald-700"
        />
      </div>

      <div className="section-card bg-[linear-gradient(135deg,#0f172a_0%,#1e293b_55%,#334155_100%)] text-white text-center p-8">
        <h3 className="text-2xl font-bold text-white">INDICASA Bias Dimensions</h3>
        <p className="mt-2 text-sm font-semibold uppercase tracking-[0.18em] text-amber-light">India-first protected attribute coverage</p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          <span className="inline-flex items-center gap-2 rounded-full bg-purple-500/20 px-4 py-2 text-sm font-medium text-purple-200 ring-1 ring-inset ring-purple-500/30">
            <span className="h-2 w-2 rounded-full bg-purple-400"></span>
            Gender
          </span>
          <span className="inline-flex items-center gap-2 rounded-full bg-orange-500/20 px-4 py-2 text-sm font-medium text-orange-200 ring-1 ring-inset ring-orange-500/30">
            <span className="h-2 w-2 rounded-full bg-orange-400"></span>
            Caste
          </span>
          <span className="inline-flex items-center gap-2 rounded-full bg-blue-500/20 px-4 py-2 text-sm font-medium text-blue-200 ring-1 ring-inset ring-blue-500/30">
            <span className="h-2 w-2 rounded-full bg-blue-400"></span>
            Religion
          </span>
          <span className="inline-flex items-center gap-2 rounded-full bg-emerald-500/20 px-4 py-2 text-sm font-medium text-emerald-200 ring-1 ring-inset ring-emerald-500/30">
            <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
            Ethnicity
          </span>
          <span className="inline-flex items-center gap-2 rounded-full bg-rose-500/20 px-4 py-2 text-sm font-medium text-rose-200 ring-1 ring-inset ring-rose-500/30">
            <span className="h-2 w-2 rounded-full bg-rose-400"></span>
            Disability
          </span>
          <span className="inline-flex items-center gap-2 rounded-full bg-yellow-500/20 px-4 py-2 text-sm font-medium text-yellow-200 ring-1 ring-inset ring-yellow-500/30">
            <span className="h-2 w-2 rounded-full bg-yellow-400"></span>
            Region
          </span>
        </div>
        <p className="mt-6 text-sm text-slate-300">
          FairFlow detects proxy bias across all 6 dimensions — the only auditing platform built for India's social context.
        </p>
      </div>

      <div className="rounded-xl border border-orange-200 bg-orange-50/30 p-6">
        <p className="text-xs font-semibold text-orange-600 tracking-widest uppercase mb-2">
          India-First Compliance
        </p>
        <h3 className="text-xl font-bold text-slate-900 mb-3">
          Built for India's Social Reality
        </h3>
        
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="rounded-lg bg-white border border-orange-100 p-3">
            <p className="text-xs text-slate-500">
              Protected by
            </p>
            <p className="text-sm font-bold text-slate-900">
              Article 15 & 16
            </p>
            <p className="text-xs text-slate-500">
              Constitution of India
            </p>
          </div>
          <div className="rounded-lg bg-white border border-orange-100 p-3">
            <p className="text-xs text-slate-500">
              SC/ST Protection
            </p>
            <p className="text-sm font-bold text-slate-900">
              Atrocities Act 1989
            </p>
            <p className="text-xs text-slate-500">
              Employment provisions
            </p>
          </div>
          <div className="rounded-lg bg-white border border-orange-100 p-3">
            <p className="text-xs text-slate-500">
              Lending fairness
            </p>
            <p className="text-sm font-bold text-slate-900">
              RBI Fair Practice Code
            </p>
            <p className="text-xs text-slate-500">
              Equal credit access
            </p>
          </div>
          <div className="rounded-lg bg-white border border-orange-100 p-3">
            <p className="text-xs text-slate-500">
              Healthcare equity
            </p>
            <p className="text-sm font-bold text-slate-900">
              NHP 2017
            </p>
            <p className="text-xs text-slate-500">
              Universal health coverage
            </p>
          </div>
        </div>
        
        <p className="text-sm text-slate-600">
          FairFlow is the only bias auditing platform that detects caste, religion, and regional discrimination — the three forms of bias most common in Indian workplaces, banks, and hospitals.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <div className="section-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Hire Rates</p>
              <h3 className="mt-2 text-2xl font-bold text-slate-900">Latest audit by gender</h3>
            </div>
          </div>
          <div className="mt-6 h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={genderData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="group" tick={{ fill: "#475569" }} />
                <YAxis tick={{ fill: "#475569" }} />
                <Tooltip formatter={(value) => [`${value}%`, "Hire Rate"]} />
                <Bar dataKey="rate" radius={[12, 12, 0, 0]}>
                  {genderData.map((entry) => (
                    <Cell key={entry.group} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="section-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">
                Ethnicity Breakdown
              </p>
              <h3 className="mt-2 text-2xl font-bold text-slate-900">Latest audit by ethnicity</h3>
            </div>
          </div>
          <div className="mt-6 h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ethnicityData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="group" tick={{ fill: "#475569", fontSize: 12 }} />
                <YAxis tick={{ fill: "#475569" }} />
                <Tooltip formatter={(value) => [`${value}%`, "Hire Rate"]} />
                <Bar dataKey="rate" radius={[12, 12, 0, 0]}>
                  {ethnicityData.map((entry) => (
                    <Cell key={entry.group} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
        <div className="section-card">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Score Trend</p>
            <h3 className="mt-2 text-2xl font-bold text-slate-900">Fairness score over last 5 audits</h3>
          </div>
          <div className="mt-6 h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={{ fill: "#475569" }} />
                <YAxis domain={[0, 100]} tick={{ fill: "#475569" }} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="fairnessScore"
                  stroke="#f59e0b"
                  strokeWidth={3}
                  dot={{ r: 5, fill: "#f59e0b" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="section-card">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Recent Audits</p>
              <h3 className="mt-2 text-2xl font-bold text-slate-900">Audit history</h3>
            </div>
            <Link
              to="/audit"
              className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-amber hover:text-amber-dark"
            >
              Upload new
            </Link>
          </div>
          <div className="mt-6 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500">
                  <th className="px-3 py-3 font-semibold">Dataset</th>
                  <th className="px-3 py-3 font-semibold">Date</th>
                  <th className="px-3 py-3 font-semibold">Candidates</th>
                  <th className="px-3 py-3 font-semibold">Score</th>
                  <th className="px-3 py-3 font-semibold">Status</th>
                  <th className="px-3 py-3 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {audits.slice(0, 5).map((audit) => (
                  <tr key={audit.id} className="border-b border-slate-100">
                    <td className="px-3 py-4 font-medium text-slate-900">
                      <div className="flex flex-col gap-2">
                        <span>{audit.dataset_name}</span>
                        <span
                          className={`inline-flex w-fit rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${
                            domainBadgeStyles[domainKey(audit)] || domainBadgeStyles.custom
                          }`}
                        >
                          {domainLabel(audit)}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-4 text-slate-600">
                      {new Date(audit.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-3 py-4 text-slate-600">{audit.total_candidates}</td>
                    <td className="px-3 py-4">
                      <span className="rounded-full bg-slate-100 px-3 py-1 font-semibold text-slate-700">
                        {Math.round(audit.fairness_score)}%
                      </span>
                    </td>
                    <td className="px-3 py-4">
                      <span
                        className={`rounded-full px-3 py-1 font-semibold ${
                          audit.mitigation_applied
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-amber-100 text-amber-dark"
                        }`}
                      >
                        {audit.mitigation_applied ? "Mitigated" : "Review Needed"}
                      </span>
                    </td>
                    <td className="px-3 py-4">
                       <div className="flex flex-wrap gap-2">
                        <Link
                          to={`/candidates/${audit.id}`}
                          className="rounded-full border border-slate-200 px-3 py-1 font-medium text-slate-700 transition hover:border-amber hover:text-amber-dark"
                        >
                          Candidates
                        </Link>
                        <Link
                          to={`/mitigate/${audit.id}`}
                          className="rounded-full border border-slate-200 px-3 py-1 font-medium text-slate-700 transition hover:border-amber hover:text-amber-dark"
                        >
                          Mitigate
                        </Link>
                        <button
                          onClick={() => handleDelete(audit.id, audit.dataset_name)}
                          disabled={deletingId === audit.id}
                          title="Delete audit (GDPR right to erasure)"
                          className="rounded-full border border-rose-200 px-3 py-1 font-medium text-rose-600 transition hover:border-rose-400 hover:bg-rose-50 disabled:opacity-50"
                        >
                          {deletingId === audit.id ? (
                            <span className="flex items-center gap-1">
                              <div className="h-3 w-3 animate-spin rounded-full border-2 border-rose-400 border-t-transparent" />
                              Deleting...
                            </span>
                          ) : (
                            <span className="flex items-center gap-1">
                              <Trash2 className="h-3 w-3" />
                              Delete
                            </span>
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
