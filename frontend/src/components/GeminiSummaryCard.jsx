import { useState, useEffect } from "react";

export default function GeminiSummaryCard({ auditId }) {
  console.log("GeminiSummaryCard mounted, auditId:", auditId);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!auditId) return;
    
    console.log("Fetching gemini summary for:", auditId);
    
    const token = localStorage.getItem("token") || 
      localStorage.getItem("access_token") || 
      sessionStorage.getItem("token") || 
      localStorage.getItem("fairlens_token");

    fetch(`http://localhost:8000/audit/${auditId}/gemini-summary`, {
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json"
      }
    })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(d => {
        console.log("Gemini summary response:", d);
        setData(d);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Gemini summary error:", err);
        setLoading(false);
      });
  }, [auditId]);

  const handleCopy = () => {
    const text = `${data.summary}\n\n${data.bottom_line}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const riskColors = {
    high: "bg-red-100 text-red-700 border-red-200",
    medium: "bg-amber-100 text-amber-700 border-amber-200",
    low: "bg-green-100 text-green-700 border-green-200"
  };

  const riskLabels = {
    high: "High Risk",
    medium: "Medium Risk", 
    low: "Low Risk"
  };

  if (!auditId) return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-6">
      <p className="text-amber-700 text-sm font-medium">
        ✨ AI Fairness Verdict — Loading audit data...
      </p>
    </div>
  );

  if (loading) return (
    <div className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xl">✨</span>
        <p className="text-xs font-semibold text-amber-600 tracking-widest uppercase">
          AI Fairness Verdict
        </p>
      </div>
      <p className="text-slate-500 text-sm">
        Generating Gemini analysis...
      </p>
    </div>
  );

  if (!data) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-xl">✨</span>
          <div>
            <p className="text-xs font-semibold text-amber-600 tracking-widest uppercase">
              AI Fairness Verdict
            </p>
            <h3 className="text-lg font-bold text-slate-900">
              Gemini Analysis
            </h3>
          </div>
        </div>
        <span className={`text-xs font-semibold px-3 py-1 rounded-full border ${riskColors[data.risk_level]}`}>
          {riskLabels[data.risk_level]}
        </span>
      </div>

      <div className="text-slate-700 text-sm leading-relaxed mb-4 space-y-3">
        {data.summary.split('\n\n').map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>

      {data.bottom_line && (
        <div className="bg-slate-900 rounded-lg p-4 mb-4">
          <p className="text-white font-semibold text-sm">
            {data.bottom_line}
          </p>
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleCopy}
          className="flex items-center gap-2 px-4 py-2 text-sm border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-700 transition-colors"
        >
          {copied ? "✓ Copied!" : "Copy for stakeholders"}
        </button>
      </div>
    </div>
  );
}
