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
import { ArrowUpRight, FolderSearch, Gauge, ShieldAlert, ShieldCheck, Users } from "lucide-react";
import { Link } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";

import { LAST_AUDIT_STORAGE_KEY, listAudits } from "../api/fairlensApi";

const ethnicityColors = ["#2563eb", "#ec4899", "#16a34a", "#f97316"];

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

  useEffect(() => {
    const fetchAudits = async () => {
      setLoading(true);
      try {
        const data = await listAudits();
        setAudits(data);
        if (data[0]?.id) {
          localStorage.setItem(LAST_AUDIT_STORAGE_KEY, data[0].id);
        }
      } catch (error) {
        setAudits([]);
      } finally {
        setLoading(false);
      }
    };

    fetchAudits();
  }, []);

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
        value: latestAudit?.dataset_name || "No dataset yet",
        compact: true,
        title: latestAudit?.dataset_name || "No dataset yet"
      },
      {
        label: "Latest Score",
        value: latestAudit ? `${Math.round(latestAudit.fairness_score)} / 100` : "0 / 100",
        compact: false,
        title: latestAudit ? `${Math.round(latestAudit.fairness_score)} / 100` : "0 / 100"
      },
      {
        label: "Flagged Candidates",
        value: latestAudit?.flagged_candidates ?? 0,
        compact: false,
        title: String(latestAudit?.flagged_candidates ?? 0)
      },
      {
        label: "Mitigation",
        value: latestAudit?.mitigation_applied ? "Applied" : "Pending",
        compact: false,
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
      <div className="section-card flex min-h-[420px] flex-col items-center justify-center text-center">
        <div className="rounded-full bg-amber/10 p-4 text-amber-dark">
          <FolderSearch className="h-8 w-8" />
        </div>
        <h2 className="mt-6 text-3xl font-bold text-slate-900">No audits yet</h2>
        <p className="mt-3 max-w-xl text-sm leading-7 text-slate-500">
          Upload your first hiring dataset to generate fairness metrics, candidate explanations,
          and mitigation recommendations.
        </p>
        <Link
          to="/audit"
          className="mt-8 inline-flex items-center rounded-2xl bg-navy px-5 py-3 text-sm font-semibold text-white transition hover:bg-navy-light"
        >
          Start Your First Audit
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="section-card overflow-hidden bg-[linear-gradient(135deg,#0f172a_0%,#1e293b_55%,#334155_100%)] text-white">
        <div className="grid gap-8 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-amber-light">Operations Pulse</p>
            <h1 className="mt-4 text-4xl font-extrabold leading-tight">
              Fairness oversight for hiring systems, in one decision cockpit.
            </h1>
            <p className="mt-5 max-w-2xl text-sm leading-7 text-slate-300">
              Track risk, investigate candidate-level bias signals, and compare mitigation outcomes
              before those rankings reach your recruiting teams.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {heroStats.map((item) => (
              <div key={item.label} className="min-w-0 rounded-3xl border border-white/10 bg-white/5 p-5">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-400">{item.label}</p>
                <p
                  className={`mt-3 font-bold text-white ${
                    item.compact ? "truncate text-lg xl:text-xl" : "text-xl xl:text-2xl"
                  }`}
                  title={item.title}
                >
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
                    <td className="px-3 py-4 font-medium text-slate-900">{audit.dataset_name}</td>
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
