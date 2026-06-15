import { useState } from "react";

const SAMPLE_JD = `We are looking for a 
rockstar engineer who is aggressive about 
results and can dominate in a fast-paced 
environment. The ideal candidate is a 
young, energetic self-starter who works 
independently and crushes deadlines. 
Must be a wizard with React and a ninja 
with backend systems.`;

export default function JobDescriptionAudit() {
  const [jdText, setJdText] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleAnalyze = async () => {
    if (!jdText.trim()) return;
    setLoading(true);
    setError(null);
    
    try {
      const token = 
        localStorage.getItem("token") ||
        localStorage.getItem("access_token");
        
      const response = await fetch(
        "http://localhost:8000/jd-audit/analyze",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`,
          },
          body: JSON.stringify({
            job_description: jdText,
            job_title: jobTitle,
          }),
        }
      );
      
      if (!response.ok) throw new Error();
      const data = await response.json();
      setResult(data);
      
    } catch {
      setError("Analysis failed. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const scoreColor = result ? (
    result.bias_score >= 80 
      ? "text-green-600" 
      : result.bias_score >= 60 
      ? "text-amber-600" 
      : "text-red-600"
  ) : "";

  const scoreBg = result ? (
    result.bias_score >= 80 
      ? "bg-green-50 border-green-200" 
      : result.bias_score >= 60 
      ? "bg-amber-50 border-amber-200" 
      : "bg-red-50 border-red-200"
  ) : "";

  return (
    <div className="max-w-4xl mx-auto space-y-6 p-6">
      
      {/* Header */}
      <div>
        <p className="text-xs font-semibold text-amber-600 tracking-widest uppercase">
          Proactive Bias Prevention
        </p>
        <h1 className="text-3xl font-bold text-slate-900 mt-1">
          Job Description Bias Detector
        </h1>
        <p className="text-slate-600 mt-2">
          Detect biased language before your job post goes live. Powered by Gemini 1.5 Flash.
        </p>
      </div>

      {/* Input */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-4">
        <div>
          <label className="text-sm font-semibold text-slate-700 block mb-1">
            Job Title (optional)
          </label>
          <input
            value={jobTitle}
            onChange={e => setJobTitle(e.target.value)}
            placeholder="e.g. Senior Software Engineer"
            className="w-full rounded-lg border border-slate-200 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
          />
        </div>
        
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm font-semibold text-slate-700">
              Job Description
            </label>
            <button
              onClick={() => setJdText(SAMPLE_JD)}
              className="text-xs text-amber-600 underline hover:no-underline"
            >
              Load biased example
            </button>
          </div>
          <textarea
            value={jdText}
            onChange={e => setJdText(e.target.value)}
            rows={8}
            placeholder="Paste your job description here..."
            className="w-full rounded-lg border border-slate-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 resize-none"
          />
          <p className="text-xs text-slate-400 mt-1">
            {jdText.split(' ').filter(Boolean).length} words
          </p>
        </div>

        <button
          onClick={handleAnalyze}
          disabled={loading || !jdText.trim()}
          className="w-full rounded-xl bg-slate-900 py-3 text-sm font-bold text-white hover:bg-slate-800 transition-colors disabled:opacity-50"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"/>
              Analyzing with Gemini...
            </span>
          ) : (
            "Analyze for Bias →"
          )}
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">
            {error}
          </p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          
          {/* Score Card */}
          <div className={`rounded-xl border p-6 ${scoreBg}`}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">
                  Inclusivity Score
                </p>
                <p className={`text-5xl font-bold mt-1 ${scoreColor}`}>
                  {result.bias_score}
                  <span className="text-xl font-normal">/100</span>
                </p>
                <p className="text-sm text-slate-600 mt-2">
                  {result.bias_description}
                </p>
              </div>
              <div className="text-right">
                <span className={`text-xs font-bold px-3 py-1 rounded-full border ${result.sdg_compliant ? "bg-green-100 text-green-700 border-green-200" : "bg-red-100 text-red-700 border-red-200"}`}>
                  {result.sdg_compliant ? "✓ SDG 10.3 Compliant" : "✗ SDG 10.3 Review Needed"}
                </span>
              </div>
            </div>
          </div>

          {/* Flagged Words */}
          {result.total_bias_words > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <h3 className="text-base font-bold text-slate-900 mb-4">
                Flagged Language
              </h3>
              <div className="space-y-3">
                {result.male_coded_words.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-blue-600 uppercase tracking-widest mb-2">
                      Male-coded words
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {result.male_coded_words.map(w => (
                        <span key={w} className="px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
                          {w}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {result.female_coded_words.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-pink-600 uppercase tracking-widest mb-2">
                      Female-coded words
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {result.female_coded_words.map(w => (
                        <span key={w} className="px-3 py-1 rounded-full text-xs font-medium bg-pink-100 text-pink-800 border border-pink-200">
                          {w}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {result.exclusionary_words.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-red-600 uppercase tracking-widest mb-2">
                      Exclusionary language
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {result.exclusionary_words.map(w => (
                        <span key={w} className="px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800 border border-red-200">
                          {w}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Gemini Suggestions */}
          {result.gemini_suggestions?.length > 0 && (
            <div className="rounded-xl border border-amber-200 bg-white p-6">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-lg">✨</span>
                <h3 className="text-base font-bold text-slate-900">
                  Gemini Neutral Alternatives
                </h3>
              </div>
              <div className="space-y-3">
                {result.gemini_suggestions.map((s, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-slate-50">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-red-600 line-through">
                          {s.original}
                        </span>
                        <span className="text-slate-400">
                          →
                        </span>
                        <span className="text-sm font-semibold text-green-600">
                          {s.replacement}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-1">
                        {s.reason}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* No bias found */}
          {result.total_bias_words === 0 && (
            <div className="rounded-xl border border-green-200 bg-green-50 p-6 text-center">
              <p className="text-2xl mb-2">✓</p>
              <p className="text-base font-bold text-green-800">
                No biased language detected
              </p>
              <p className="text-sm text-green-700 mt-1">
                This job description appears inclusive and gender-neutral.
              </p>
            </div>
          )}

        </div>
      )}
    </div>
  );
}
