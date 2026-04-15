import { Dialog, Transition } from "@headlessui/react";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Search,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  X
} from "lucide-react";
import { Fragment, startTransition, useDeferredValue, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  LAST_AUDIT_STORAGE_KEY,
  explainCandidate,
  getCandidates,
  getCounterfactual
} from "../api/fairlensApi";
import CounterfactualPanel from "../components/CounterfactualPanel";
import SHAPWaterfallChart from "../components/SHAPWaterfallChart";
import Spinner from "../components/Spinner";

function Candidates() {
  const { auditId } = useParams();
  const [candidates, setCandidates] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [panelLoading, setPanelLoading] = useState(false);
  const deferredSearch = useDeferredValue(search);

  useEffect(() => {
    if (auditId) {
      localStorage.setItem(LAST_AUDIT_STORAGE_KEY, auditId);
    }
  }, [auditId]);

  useEffect(() => {
    const fetchCandidates = async () => {
      setLoading(true);
      try {
        const response = await getCandidates(auditId, {
          page,
          page_size: 20,
          search: deferredSearch,
          bias_status: filter
        });
        setCandidates(response.items);
        setTotal(response.total);
      } catch (error) {
        setCandidates([]);
        setTotal(0);
      } finally {
        setLoading(false);
      }
    };

    fetchCandidates();
  }, [auditId, deferredSearch, filter, page]);

  const handleCandidateSelect = async (candidate) => {
    startTransition(() => {
      setSelectedCandidate(candidate);
    });

    const needsShap = !candidate.shap_values?.waterfall_data;
    const needsCounterfactual = !candidate.counterfactual_result;
    if (!needsShap && !needsCounterfactual) {
      return;
    }

    setPanelLoading(true);
    try {
      const [shapData, counterfactualData] = await Promise.all([
        needsShap ? explainCandidate(candidate.id) : Promise.resolve(candidate.shap_values),
        needsCounterfactual ? getCounterfactual(candidate.id) : Promise.resolve(candidate.counterfactual_result)
      ]);
      startTransition(() => {
        setSelectedCandidate({
          ...candidate,
          shap_values: shapData,
          counterfactual_result: counterfactualData
        });
      });
    } catch (error) {
      return;
    } finally {
      setPanelLoading(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="space-y-6">
      <div className="section-card">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">
              Candidate Explorer
            </p>
            <h1 className="mt-3 text-4xl font-extrabold text-slate-900">Review flagged candidate decisions</h1>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">
              Search the current audit, filter bias flags, and open the slide-in review panel for
              SHAP explanations and protected-attribute counterfactual checks.
            </p>
            <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-indigo-700">
              What-If Sandbox: Click Any Candidate to Simulate Counterfactual Outcomes
            </div>
          </div>
          <div className="rounded-3xl bg-navy p-5 text-white shadow-glow">
            <p className="text-xs uppercase tracking-[0.18em] text-amber-light">Audit Scope</p>
            <p className="mt-2 text-2xl font-bold">{total} candidates</p>
            <p className="mt-2 text-sm text-slate-300">20 per page with saved candidate explanations</p>
          </div>
        </div>
      </div>

      <div className="section-card">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative w-full max-w-xl">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(event) => {
                setPage(1);
                setSearch(event.target.value);
              }}
              className="w-full rounded-2xl border-slate-200 bg-slate-50 px-12 py-3 focus:border-amber focus:ring-amber"
              placeholder="Search by candidate name"
            />
          </div>
          <div className="flex items-center gap-3">
            <div className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-medium text-slate-600">
              <SlidersHorizontal className="h-4 w-4" />
              Bias status
            </div>
            <select
              value={filter}
              onChange={(event) => {
                setPage(1);
                setFilter(event.target.value);
              }}
              className="rounded-2xl border-slate-200 bg-white px-4 py-3 text-sm font-medium focus:border-amber focus:ring-amber"
            >
              <option value="all">All</option>
              <option value="flagged">Flagged</option>
              <option value="clean">Clean</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="flex min-h-[240px] items-center justify-center">
            <Spinner className="h-8 w-8 text-navy" />
          </div>
        ) : !candidates.length ? (
          <div className="flex min-h-[260px] flex-col items-center justify-center text-center">
            <ShieldCheck className="h-10 w-10 text-slate-300" />
            <h2 className="mt-5 text-2xl font-bold text-slate-900">No candidates matched this view</h2>
            <p className="mt-3 max-w-lg text-sm leading-7 text-slate-500">
              Adjust the search term or filter, or upload a new audit if this workspace does not
              have candidate data yet.
            </p>
            <Link
              to="/audit"
              className="mt-6 rounded-2xl bg-navy px-5 py-3 text-sm font-semibold text-white transition hover:bg-navy-light"
            >
              Upload Another Audit
            </Link>
          </div>
        ) : (
          <>
            <div className="mt-6 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="px-3 py-3 font-semibold">Name</th>
                    <th className="px-3 py-3 font-semibold">Gender</th>
                    <th className="px-3 py-3 font-semibold">Ethnicity</th>
                    <th className="px-3 py-3 font-semibold">Experience</th>
                    <th className="px-3 py-3 font-semibold">Decision</th>
                    <th className="px-3 py-3 font-semibold">Bias Flag</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((candidate) => (
                    <tr
                      key={candidate.id}
                      onClick={() => handleCandidateSelect(candidate)}
                      className="cursor-pointer border-b border-slate-100 transition hover:bg-amber/5"
                    >
                      <td className="px-3 py-4 font-medium text-slate-900">{candidate.name}</td>
                      <td className="px-3 py-4 text-slate-600">{candidate.gender}</td>
                      <td className="px-3 py-4 text-slate-600">{candidate.ethnicity}</td>
                      <td className="px-3 py-4 text-slate-600">{candidate.years_experience} years</td>
                      <td className="px-3 py-4">
                        <span
                          className={`rounded-full px-3 py-1 font-semibold ${
                            candidate.original_decision
                              ? "bg-emerald-100 text-emerald-700"
                              : "bg-rose-100 text-rose-700"
                          }`}
                        >
                          {candidate.original_decision ? "Hired" : "Rejected"}
                        </span>
                      </td>
                      <td className="px-3 py-4">
                        {candidate.bias_flagged ? (
                          <span className="inline-flex items-center gap-2 rounded-full bg-amber-100 px-3 py-1 font-semibold text-amber-dark">
                            <ShieldAlert className="h-4 w-4" />
                            Flagged
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-3 py-1 font-semibold text-emerald-700">
                            <ShieldCheck className="h-4 w-4" />
                            Clean
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-slate-500">
                Showing page {page} of {totalPages}
              </p>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={page === 1}
                  className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                  disabled={page === totalPages}
                  className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      <Transition.Root show={Boolean(selectedCandidate)} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => setSelectedCandidate(null)}>
          <Transition.Child
            as={Fragment}
            enter="transition-opacity duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="transition-opacity duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-hidden">
            <div className="absolute inset-0 overflow-hidden">
              <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-6">
                <Transition.Child
                  as={Fragment}
                  enter="transform transition duration-300"
                  enterFrom="translate-x-full"
                  enterTo="translate-x-0"
                  leave="transform transition duration-200"
                  leaveFrom="translate-x-0"
                  leaveTo="translate-x-full"
                >
                  <Dialog.Panel className="pointer-events-auto w-screen max-w-3xl">
                    <div className="flex h-full flex-col bg-slate-50 shadow-xl">
                      <div className="border-b border-slate-200 bg-white px-6 py-5">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <Dialog.Title className="text-2xl font-bold text-slate-900">
                              {selectedCandidate?.name}
                            </Dialog.Title>
                            <p className="mt-2 text-sm text-slate-500">
                              {selectedCandidate?.gender} • {selectedCandidate?.ethnicity} •{" "}
                              {selectedCandidate?.years_experience} years experience
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => setSelectedCandidate(null)}
                            className="rounded-full border border-slate-200 bg-white p-2 text-slate-500"
                          >
                            <X className="h-5 w-5" />
                          </button>
                        </div>
                      </div>

                      <div className="flex-1 space-y-5 overflow-y-auto px-6 py-6">
                        {panelLoading && (
                          <div className="flex items-center gap-3 rounded-3xl border border-slate-200 bg-white p-5 text-sm text-slate-600">
                            <Spinner className="h-5 w-5 text-navy" />
                            Loading fresh candidate explainability data...
                          </div>
                        )}

                        {selectedCandidate?.shap_values?.proxy_flags?.length > 0 && (
                          <div className="flex items-start gap-3 rounded-3xl border border-amber-200 bg-amber-50 px-5 py-4 text-amber-900">
                            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
                            <p className="text-sm leading-7">
                              Proxy discrimination warning: high-importance proxy features detected in this
                              decision path ({selectedCandidate.shap_values.proxy_flags.join(", ")}).
                            </p>
                          </div>
                        )}

                        <div className="grid gap-4 md:grid-cols-3">
                          <div className="rounded-3xl border border-slate-200 bg-white p-4">
                            <p className="text-sm font-medium text-slate-500">Education</p>
                            <p className="mt-2 text-lg font-bold text-slate-900">
                              {selectedCandidate?.education_level}
                            </p>
                          </div>
                          <div className="rounded-3xl border border-slate-200 bg-white p-4">
                            <p className="text-sm font-medium text-slate-500">Original Decision</p>
                            <p className="mt-2 text-lg font-bold text-slate-900">
                              {selectedCandidate?.original_decision ? "Hired" : "Rejected"}
                            </p>
                          </div>
                          <div className="rounded-3xl border border-slate-200 bg-white p-4">
                            <p className="text-sm font-medium text-slate-500">Bias Status</p>
                            <p className="mt-2 text-lg font-bold text-slate-900">
                              {selectedCandidate?.bias_flagged ? "Flagged" : "Clean"}
                            </p>
                          </div>
                        </div>

                        <SHAPWaterfallChart
                          waterfallData={selectedCandidate?.shap_values?.waterfall_data || []}
                        />
                        <CounterfactualPanel result={selectedCandidate?.counterfactual_result} />
                      </div>
                    </div>
                  </Dialog.Panel>
                </Transition.Child>
              </div>
            </div>
          </div>
        </Dialog>
      </Transition.Root>
    </div>
  );
}

export default Candidates;
