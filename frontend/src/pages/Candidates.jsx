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
  getAudit,
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
  const [audit, setAudit] = useState(null);
  const [domainConfig, setDomainConfig] = useState({
    subject_label: "Candidate",
    outcome_label: "Hired",
    protected_attributes: ["gender", "ethnicity", "age"],
    feature_columns: ["years_experience"],
    column_map: {}
  });
  const deferredSearch = useDeferredValue(search);

  useEffect(() => {
    if (auditId) {
      localStorage.setItem(LAST_AUDIT_STORAGE_KEY, auditId);
    }
  }, [auditId]);

  useEffect(() => {
    const fetchAudit = async () => {
      try {
        const auditData = await getAudit(auditId);
        setAudit(auditData);
        setDomainConfig(
          auditData?.domain_config || {
            subject_label: "Candidate",
            outcome_label: "Hired",
            protected_attributes: ["gender", "ethnicity", "age"],
            feature_columns: ["years_experience"],
            column_map: {}
          }
        );
      } catch (error) {
        setAudit(null);
        setDomainConfig({
          subject_label: "Candidate",
          outcome_label: "Hired",
          protected_attributes: ["gender", "ethnicity", "age"],
          feature_columns: ["years_experience"],
          column_map: {}
        });
      }
    };
    fetchAudit();
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

  const handleCandidateSelect = async (candidate, displayIndex) => {
    startTransition(() => {
      setSelectedCandidate({ ...candidate, displayIndex });
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
          displayIndex,
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
  const subjectLabel = domainConfig?.subject_label || "Candidate";
  const outcomeLabel = domainConfig?.outcome_label || "Hired";
  const columnMap = domainConfig?.column_map || {};
  const protectedAttributes = domainConfig?.protected_attributes || ["gender", "ethnicity", "age"];
  const featureColumns = domainConfig?.feature_columns || ["years_experience"];
  const primaryProtected = protectedAttributes[0] || "gender";
  const secondaryProtected = protectedAttributes[1] || "ethnicity";
  const primaryFeature = featureColumns[0] || "years_experience";
  const secondaryFeature = featureColumns[1] || "education_level";

  const getValue = (candidate, column) => {
    if (candidate?.[column] !== undefined) {
      return candidate[column];
    }
    if (candidate?.feature_payload?.[column] !== undefined) {
      return candidate.feature_payload[column];
    }
    return "N/A";
  };

  const femaleCount = candidates.filter(c => String(getValue(c, primaryProtected)).toLowerCase() === 'female').length;
  const maleCount = candidates.filter(c => String(getValue(c, primaryProtected)).toLowerCase() === 'male').length;
  const totalGender = femaleCount + maleCount || 1;
  const femalePct = Math.round((femaleCount / totalGender) * 100);
  const malePct = Math.round((maleCount / totalGender) * 100);

  return (
    <div className="space-y-6">
      <div className="section-card">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">
              {subjectLabel} Explorer
            </p>
            <h1 className="mt-3 text-4xl font-extrabold text-slate-900">Review flagged {subjectLabel.toLowerCase()} decisions</h1>
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
            <p className="mt-2 text-2xl font-bold">{total} {subjectLabel.toLowerCase()}s</p>
            <p className="mt-2 text-sm text-slate-300">20 per page with saved explainability snapshots</p>
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
              placeholder={`Search by ${subjectLabel.toLowerCase()} name`}
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
            <h2 className="mt-5 text-2xl font-bold text-slate-900">No {subjectLabel.toLowerCase()}s matched this view</h2>
            <p className="mt-3 max-w-lg text-sm leading-7 text-slate-500">
              Adjust the search term or filter, or upload a new audit if this workspace does not
              have {subjectLabel.toLowerCase()} data yet.
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
            <div className="mt-6 flex flex-col gap-4 rounded-2xl bg-slate-50 p-4 sm:flex-row sm:items-center sm:justify-between border border-slate-200">
              <div className="text-sm font-medium text-slate-700">
                Showing {total} {subjectLabel.toLowerCase()}s • {audit?.flagged_candidates || 0} flagged • Filter: {filter === "all" ? "All" : filter === "flagged" ? "Flagged" : "Clean"}
              </div>
              <div className="text-sm font-medium text-slate-700">
                Gender split: {femalePct}% Female • {malePct}% Male
              </div>
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="px-3 py-3 font-semibold">{columnMap.name || "name"}</th>
                    <th className="px-3 py-3 font-semibold">{primaryProtected}</th>
                    <th className="px-3 py-3 font-semibold">{secondaryProtected}</th>
                    <th className="px-3 py-3 font-semibold">{primaryFeature}</th>
                    <th className="px-3 py-3 font-semibold">{outcomeLabel}</th>
                    <th className="px-3 py-3 font-semibold">Bias Flag</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((candidate, index) => {
                    const displayIndex = ((page - 1) * 20) + index + 1;
                    return (
                    <tr
                      key={candidate.id}
                      onClick={() => handleCandidateSelect(candidate, displayIndex)}
                      className={`cursor-pointer border-b border-slate-100 transition hover:bg-amber/5 ${
                        candidate.bias_flagged ? "border-l-4 border-l-amber-400" : "border-l-4 border-l-transparent"
                      }`}
                    >
                      <td className="px-3 py-4 font-medium text-slate-900">
                        <div className="group relative inline-block">
                          <span>Candidate #{displayIndex}</span>
                          <div className="absolute bottom-full left-1/2 z-10 mb-2 hidden -translate-x-1/2 whitespace-nowrap rounded bg-slate-800 px-2 py-1 text-xs text-white group-hover:block">
                            Hash: {getValue(candidate, "name")}
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-4">
                        <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">
                          {String(getValue(candidate, primaryProtected))}
                        </span>
                      </td>
                      <td className="px-3 py-4">
                        <span className="inline-flex items-center rounded-full bg-purple-50 px-2 py-1 text-xs font-medium text-purple-700 ring-1 ring-inset ring-purple-700/10">
                          {String(getValue(candidate, secondaryProtected))}
                        </span>
                      </td>
                      <td className="px-3 py-4 text-slate-600">{String(getValue(candidate, primaryFeature))}</td>
                      <td className="px-3 py-4">
                        <span
                          className={`rounded-full px-3 py-1 font-semibold ${
                            candidate.original_decision
                              ? "bg-emerald-100 text-emerald-700"
                              : "bg-rose-100 text-rose-700"
                          }`}
                        >
                          {candidate.original_decision ? outcomeLabel : `Not ${outcomeLabel}`}
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
                  )})}
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
                              Candidate #{selectedCandidate?.displayIndex}
                            </Dialog.Title>
                            <p className="mt-2 text-sm text-slate-500">
                              {selectedCandidate?.gender} • {selectedCandidate?.ethnicity} •{" "}
                              {String(getValue(selectedCandidate, primaryFeature))}
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
                            Loading fresh {subjectLabel.toLowerCase()} explainability data...
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
                            <p className="text-sm font-medium text-slate-500">{secondaryFeature}</p>
                            <p className="mt-2 text-lg font-bold text-slate-900">
                              {String(getValue(selectedCandidate, secondaryFeature))}
                            </p>
                          </div>
                          <div className="rounded-3xl border border-slate-200 bg-white p-4">
                            <p className="text-sm font-medium text-slate-500">Original Decision</p>
                            <p className="mt-2 text-lg font-bold text-slate-900">
                              {selectedCandidate?.original_decision ? outcomeLabel : `Not ${outcomeLabel}`}
                            </p>
                          </div>
                          <div className="rounded-3xl border border-slate-200 bg-white p-4">
                            <p className="text-sm font-medium text-slate-500">Bias Status</p>
                            <p className="mt-2 text-lg font-bold text-slate-900">
                              {selectedCandidate?.bias_flagged ? "Flagged" : "Clean"}
                            </p>
                          </div>
                        </div>

                        {selectedCandidate?.shap_values?.waterfall_data?.length > 0 ? (
                          <SHAPWaterfallChart
                            waterfallData={selectedCandidate.shap_values.waterfall_data}
                          />
                        ) : (
                          <div className="rounded-3xl border border-slate-200 bg-slate-50 p-8 text-center">
                            <p className="text-sm font-medium text-slate-500">Explainability snapshot not available for this record</p>
                          </div>
                        )}
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
