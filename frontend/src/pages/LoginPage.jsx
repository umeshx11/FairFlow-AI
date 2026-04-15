import { ArrowRight, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { login, persistSession } from "../api/fairlensApi";
import Spinner from "../components/Spinner";

function LoginPage() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    email: "",
    password: ""
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    try {
      const response = await login(formData);
      persistSession(response);
      navigate("/dashboard", { replace: true });
    } catch (error) {
      return;
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="soft-grid flex min-h-screen items-center justify-center px-4 py-10">
      <div className="glass-panel grid w-full max-w-5xl overflow-hidden lg:grid-cols-[1.05fr_0.95fr]">
        <div className="relative overflow-hidden bg-navy px-8 py-12 text-white sm:px-12">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(245,158,11,0.22),transparent_28%),radial-gradient(circle_at_bottom_left,rgba(255,255,255,0.06),transparent_30%)]" />
          <div className="relative">
            <div className="inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-200">
              <ShieldCheck className="h-5 w-5 text-amber-light" />
              Bias detection platform
            </div>
            <h1 className="mt-8 max-w-md text-4xl font-extrabold leading-tight">
              Make hiring decisions visible, explainable, and fair.
            </h1>
            <p className="mt-5 max-w-lg text-base leading-7 text-slate-300">
              FairFlow AI combines fairness metrics, counterfactual analysis, SHAP explanations,
              and mitigation workflows so hiring teams can act on bias instead of guessing.
            </p>
            <div className="mt-10 grid gap-4 sm:grid-cols-2">
              {[
                "Upload CSV audits in one flow",
                "Track disparate impact and opportunity gaps",
                "Inspect candidate-level proxy signals",
                "Apply mitigation strategies before rollout"
              ].map((item) => (
                <div key={item} className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200">
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-white px-8 py-12 sm:px-12">
          <div className="mx-auto max-w-md">
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-amber-dark">
              Welcome Back
            </p>
            <h2 className="mt-4 text-3xl font-bold text-slate-900">Sign in to FairFlow AI</h2>
            <p className="mt-3 text-sm leading-6 text-slate-500">
              Continue to your dashboards, audit history, and candidate fairness reviews.
            </p>

            <form className="mt-10 space-y-5" onSubmit={handleSubmit}>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">Work Email</label>
                <input
                  type="email"
                  required
                  value={formData.email}
                  onChange={(event) => setFormData((current) => ({ ...current, email: event.target.value }))}
                  className="w-full rounded-2xl border-slate-200 bg-slate-50 px-4 py-3 focus:border-amber focus:ring-amber"
                  placeholder="you@company.com"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-700">Password</label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={formData.password}
                  onChange={(event) => setFormData((current) => ({ ...current, password: event.target.value }))}
                  className="w-full rounded-2xl border-slate-200 bg-slate-50 px-4 py-3 focus:border-amber focus:ring-amber"
                  placeholder="Enter your password"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-navy px-4 py-3 text-sm font-semibold text-white transition hover:bg-navy-light disabled:cursor-not-allowed disabled:opacity-70"
              >
                {loading ? <Spinner /> : <ArrowRight className="h-4 w-4" />}
                {loading ? "Signing in..." : "Sign In"}
              </button>
            </form>

            <p className="mt-6 text-sm text-slate-500">
              New to the platform?{" "}
              <Link to="/register" className="font-semibold text-amber-dark transition hover:text-amber">
                Create an account
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
