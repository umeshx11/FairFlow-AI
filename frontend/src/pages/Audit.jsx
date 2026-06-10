import { CheckCircle2, ChevronRight, LockKeyhole, Sparkles, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { useNavigate } from "react-router-dom";

import { LAST_AUDIT_STORAGE_KEY, getAuditTemplates, uploadAudit } from "../api/fairlensApi";
import CSVUploader from "../components/CSVUploader";
import DomainSelector from "../components/DomainSelector";
import FairnessReportCard from "../components/FairnessReportCard";
import GeminiSummaryCard from "../components/GeminiSummaryCard";
import LocalWasmPrecheckCard from "../components/LocalWasmPrecheckCard";
import ResumeImageUploader from "../components/ResumeImageUploader";
import { buildEthosInputFromCsvText } from "../wasm/csvAuditInput";
import { runEthosPipeline } from "../wasm/ethosEngine";
import { sanitizeCsvForUpload } from "../wasm/privacyShield";

const wizardSteps = [
  { id: 1, label: "Domain Selection" },
  { id: 2, label: "CSV Upload" }
];

const normalizeHeader = (header) =>
  String(header || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/-/g, "_");

const parseCsvList = (value) =>
  String(value || "")
    .split(",")
    .map((item) => normalizeHeader(item))
    .filter(Boolean);

function Audit() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [report, setReport] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [localPrecheck, setLocalPrecheck] = useState(null);
  const [proxyColumn, setProxyColumn] = useState("years_experience");
  const [privacySummary, setPrivacySummary] = useState(null);
  const [headerValidation, setHeaderValidation] = useState({ found: [], missing: [], allHeaders: [] });
  const [outcomeColumn, setOutcomeColumn] = useState("hired");
  const [protectedAttrs, setProtectedAttrs] = useState("gender,ethnicity,age");
  const [featureColumns, setFeatureColumns] = useState("years_experience,education_level");
  const [requiredColumns, setRequiredColumns] = useState("");
  const [subjectLabel, setSubjectLabel] = useState("Candidate");
  const [outcomeLabel, setOutcomeLabel] = useState("Hired");
  const [outcomePositiveValue, setOutcomePositiveValue] = useState("1");
  const [showAdvancedSchema, setShowAdvancedSchema] = useState(false);
  const [geminiData, setGeminiData] = useState(null);
  const [geminiLoading, setGeminiLoading] = useState(false);

  useEffect(() => {
    const auditId = report?.audit?.id;
    if (!auditId) return;
    
    setGeminiLoading(true);
    
    const token = report?.demo_token || 
      localStorage.getItem("token") || 
      localStorage.getItem("access_token") ||
      localStorage.getItem("fairlens_token");
    
    fetch(
      `http://localhost:8000/audit/${auditId}/gemini-summary`,
      {
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        }
      }
    )
    .then(r => {
      if (!r.ok) {
        throw new Error("Failed to fetch gemini summary");
      }
      return r.json();
    })
    .then(d => {
      setGeminiData(d);
      setGeminiLoading(false);
    })
    .catch(err => {
      console.error("Gemini fetch error:", err);
      setGeminiLoading(false);
      // set to a default fallback structure if you want, or just leave it null
    });
  }, [report?.audit?.id]);

  useEffect(() => {
    const loadTemplates = async () => {
      try {
        const payload = await getAuditTemplates();
        const loaded = payload?.templates || [];
        setTemplates(loaded);
        const defaultTemplate = loaded.find((item) => item.domain === "hiring") || loaded[0] || null;
        if (defaultTemplate) {
          setSelectedTemplate(defaultTemplate);
          setOutcomeColumn(defaultTemplate.outcome_column || "hired");
          setProtectedAttrs((defaultTemplate.protected_attributes || ["gender"]).join(","));
          setFeatureColumns((defaultTemplate.feature_columns || []).join(","));
          setRequiredColumns((defaultTemplate.required_columns || []).join(","));
          setSubjectLabel(defaultTemplate.subject_label || "Candidate");
          setOutcomeLabel(defaultTemplate.outcome_label || "Hired");
          setOutcomePositiveValue(String(defaultTemplate.outcome_positive_value ?? 1));
        }
      } catch (error) {
        setTemplates([]);
        setSelectedTemplate(null);
      }
    };
    loadTemplates();
  }, []);

  const currentStepLabel = wizardSteps.find((item) => item.id === step)?.label || "";

  const setDomain = (template) => {
    setSelectedTemplate(template);
    setOutcomeColumn(template.outcome_column || "hired");
    setProtectedAttrs((template.protected_attributes || ["gender"]).join(","));
    setFeatureColumns((template.feature_columns || []).join(","));
    setRequiredColumns((template.required_columns || []).join(","));
    setSubjectLabel(template.subject_label || "Record");
    setOutcomeLabel(template.outcome_label || "Outcome");
    setOutcomePositiveValue(String(template.outcome_positive_value ?? 1));
    setHeaderValidation({ found: [], missing: [], allHeaders: [] });
  };

  const handleFileSelected = async (file) => {
    if (!selectedTemplate) {
      return;
    }
    try {
      const text = await file.text();
      const firstLine = text.split(/\r?\n/).find((line) => line.trim().length > 0) || "";
      const headers = firstLine.split(",").map((header) => normalizeHeader(header));
      const selectedRequiredColumns = parseCsvList(requiredColumns);
      const required = selectedRequiredColumns.length
        ? selectedRequiredColumns
        : (selectedTemplate.required_columns || []).map((column) => normalizeHeader(column));
      const missing = required.filter((column) => !headers.includes(column));
      const found = required.filter((column) => headers.includes(column));
      setHeaderValidation({ found, missing, allHeaders: headers });
    } catch (error) {
      setHeaderValidation({ found: [], missing: ["Could not parse headers"], allHeaders: [] });
    }
  };

  const handleUpload = async (file) => {
    const selectedRequiredColumns = parseCsvList(requiredColumns);
    if (selectedTemplate && selectedRequiredColumns.length > 0 && headerValidation.missing.length > 0) {
      throw new Error(`Missing required columns: ${headerValidation.missing.join(", ")}`);
    }

    setUploading(true);
    let csvText = "";

    try {
      csvText = await file.text();
      const parsedProtectedAttrs = parseCsvList(protectedAttrs);
      const parsedFeatureColumns = parseCsvList(featureColumns);
      const localInput = buildEthosInputFromCsvText(csvText, {
        requiredHeaders: selectedRequiredColumns.length ? selectedRequiredColumns : undefined,
        protectedColumn: parsedProtectedAttrs[0] || "gender",
        outcomeColumn: normalizeHeader(outcomeColumn) || "hired",
        outcomePositiveValue,
        proxyColumn: parsedFeatureColumns[0] || "years_experience"
      });
      const localResult = await runEthosPipeline(localInput);
      setLocalPrecheck(localResult);
      setProxyColumn(localInput.proxyColumn);
    } catch (error) {
      setLocalPrecheck(null);
    }

    const formData = new FormData();
    let privacyStats = null;

    try {
      const sanitized = await sanitizeCsvForUpload(csvText || (await file.text()));
      privacyStats = sanitized.stats;
      setPrivacySummary(privacyStats);
      const sanitizedFile = new File([sanitized.csvText], file.name, { type: "text/csv" });
      formData.append("file", sanitizedFile);
    } catch (error) {
      setPrivacySummary(null);
      formData.append("file", file);
    }

    const parsedProtectedAttrs = parseCsvList(protectedAttrs);
    const parsedFeatureColumns = parseCsvList(featureColumns);

    if (selectedTemplate) {
      formData.append("domain", selectedTemplate.domain);
      formData.append(
        "domain_config",
        JSON.stringify({
          domain: selectedTemplate.domain,
          display_name:
            selectedTemplate.domain === "custom"
              ? subjectLabel || "Custom"
              : selectedTemplate.display_name || "Custom",
          outcome_column: normalizeHeader(outcomeColumn) || selectedTemplate.outcome_column,
          outcome_positive_value: Number.isNaN(Number(outcomePositiveValue))
            ? outcomePositiveValue
            : Number(outcomePositiveValue),
          protected_attributes: parsedProtectedAttrs.length
            ? parsedProtectedAttrs
            : selectedTemplate.protected_attributes,
          feature_columns: parsedFeatureColumns.length ? parsedFeatureColumns : selectedTemplate.feature_columns || [],
          outcome_label: outcomeLabel || selectedTemplate.outcome_label,
          subject_label: subjectLabel || selectedTemplate.subject_label,
          required_columns: selectedRequiredColumns.length
            ? selectedRequiredColumns
            : selectedTemplate.required_columns || [],
          column_map: selectedTemplate.column_map || {}
        })
      );
    }

    try {
      const response = await uploadAudit(formData);
      setReport(response);
      localStorage.setItem(LAST_AUDIT_STORAGE_KEY, response.audit.id);
      toast.success(
        `Upload completed. ${response?.summary?.total_candidates ?? 0} ${
          selectedTemplate.subject_label || "records"
        } analyzed${
          privacyStats && privacyStats.fieldsHashed > 0
            ? `, ${privacyStats.fieldsHashed} PII fields hashed locally`
            : ""
        }.`
      );
      return response;
    } catch (error) {
      const missingColumns = error?.response?.data?.detail?.missing_columns;
      if (Array.isArray(missingColumns) && missingColumns.length > 0) {
        throw new Error(`Missing columns: ${missingColumns.join(", ")}`);
      }
      throw error;
    } finally {
      setUploading(false);
    }
  };

  const headerRows = useMemo(() => {
    const selectedRequiredColumns = parseCsvList(requiredColumns);
    if (!selectedRequiredColumns.length && !selectedTemplate?.required_columns) {
      return [];
    }
    const requiredSource = selectedRequiredColumns.length ? selectedRequiredColumns : selectedTemplate.required_columns;
    return requiredSource.map((column) => {
      const normalized = normalizeHeader(column);
      const present = headerValidation.found.includes(normalized);
      return { column, present };
    });
  }, [headerValidation.found, requiredColumns, selectedTemplate]);

  return (
    <div className="space-y-6">
      <div className="section-card overflow-hidden bg-[linear-gradient(135deg,#fff7ed_0%,#ffffff_48%,#eff6ff_100%)]">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-amber-dark">New Audit</p>
            <h1 className="mt-4 text-4xl font-extrabold text-slate-900">Domain-agnostic fairness upload</h1>
            <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-600">
              Step {step} of 2: {currentStepLabel}. Configure domain schema first, then upload CSV for fairness analysis.
            </p>
            <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">
              <LockKeyhole className="h-4 w-4" />
              Zero Data Egress: Local Browser Privacy Shield
            </div>
          </div>
          <div className="rounded-3xl bg-navy p-5 text-white shadow-glow">
            <div className="flex items-center gap-3">
              <Sparkles className="h-6 w-6 text-amber-light" />
              <div>
                <p className="text-sm font-semibold">Audit Workflow</p>
                <p className="text-sm text-slate-300">Domain template -> CSV validation -> fairness report</p>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-wrap gap-4">
          {wizardSteps.map((wizardStep, index) => {
            const isComplete = step > wizardStep.id;
            const isActive = step === wizardStep.id;
            return (
              <div key={wizardStep.id} className="flex items-center gap-4">
                <div
                  className={`flex h-12 w-12 items-center justify-center rounded-full border-2 text-sm font-bold ${
                    isComplete
                      ? "border-emerald-500 bg-emerald-500 text-white"
                      : isActive
                        ? "border-amber bg-amber/10 text-amber-dark"
                        : "border-slate-200 bg-white text-slate-400"
                  }`}
                >
                  {isComplete ? <CheckCircle2 className="h-5 w-5" /> : wizardStep.id}
                </div>
                <p className="text-sm font-semibold text-slate-900">{wizardStep.label}</p>
                {index < wizardSteps.length - 1 && <ChevronRight className="h-4 w-4 text-slate-300" />}
              </div>
            );
          })}
        </div>
      </div>

      {step === 1 && (
        <>
          <section className="section-card border border-amber-200 bg-amber-50/30">
            <div className="flex items-center gap-3 mb-2">
              <span className="text-2xl">📸</span>
              <div>
                <p className="text-xs font-semibold text-amber-600 tracking-widest uppercase">
                  New — Multimodal Audit
                </p>
                <h3 className="text-xl font-bold text-slate-900">
                  Audit from a photo
                </h3>
              </div>
            </div>
            <p className="text-sm text-slate-600 mb-5">
              Skip the CSV. Photograph a physical resume, triage form, or application — Gemini 2.5 Pro extracts the data and runs the bias audit instantly.
            </p>
            <ResumeImageUploader 
              onExtracted={(data) => {
                console.log("Extracted candidate data:", data);
              }}
            />
          </section>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200"/>
            </div>
            <div className="relative flex justify-center">
              <span className="bg-white px-4 text-sm text-slate-500 font-medium">
                or upload a CSV dataset
              </span>
            </div>
          </div>
          <DomainSelector templates={templates} selectedDomain={selectedTemplate?.domain} onSelect={setDomain} />
          <div className="flex justify-end">
            <button
              type="button"
              disabled={!selectedTemplate}
              onClick={() => setStep(2)}
              className="rounded-2xl bg-navy px-5 py-3 text-sm font-semibold text-white transition hover:bg-navy-light disabled:cursor-not-allowed disabled:opacity-70"
            >
              Continue to Upload
            </button>
          </div>
        </>
      )}

      {step === 2 && (
        <>
          <section className="section-card border border-slate-200 bg-white">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Step 2 of 2</p>
                <h3 className="mt-2 text-2xl font-bold text-slate-900">
                  Expected columns for {selectedTemplate?.display_name || "Selected Domain"}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setStep(1)}
                className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700"
              >
                Back to Domain Selection
              </button>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <label className="space-y-2">
                <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Outcome Column</span>
                <input
                  value={outcomeColumn}
                  onChange={(event) => setOutcomeColumn(event.target.value)}
                  className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900"
                />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Protected Attributes
                </span>
                <input
                  value={protectedAttrs}
                  onChange={(event) => setProtectedAttrs(event.target.value)}
                  className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900"
                />
              </label>
            </div>

            <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Advanced Schema Controls
                </p>
                <button
                  type="button"
                  onClick={() => setShowAdvancedSchema((current) => !current)}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-amber/50 hover:text-amber-dark"
                >
                  {showAdvancedSchema ? "Hide" : "Show"}
                </button>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                Use advanced controls only if your organization needs custom labels or column remapping.
              </p>
            </div>

            {showAdvancedSchema && (
              <>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <label className="space-y-2">
                    <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Feature Columns
                    </span>
                    <input
                      value={featureColumns}
                      onChange={(event) => setFeatureColumns(event.target.value)}
                      className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900"
                    />
                  </label>
                  <label className="space-y-2">
                    <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Required Columns
                    </span>
                    <input
                      value={requiredColumns}
                      onChange={(event) => setRequiredColumns(event.target.value)}
                      className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900"
                    />
                  </label>
                </div>

                <div className="mt-4 grid gap-4 md:grid-cols-3">
                  <label className="space-y-2">
                    <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Subject Label
                    </span>
                    <input
                      value={subjectLabel}
                      onChange={(event) => setSubjectLabel(event.target.value)}
                      className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900"
                    />
                  </label>
                  <label className="space-y-2">
                    <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Outcome Label
                    </span>
                    <input
                      value={outcomeLabel}
                      onChange={(event) => setOutcomeLabel(event.target.value)}
                      className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900"
                    />
                  </label>
                  <label className="space-y-2">
                    <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Positive Outcome Value
                    </span>
                    <input
                      value={outcomePositiveValue}
                      onChange={(event) => setOutcomePositiveValue(event.target.value)}
                      className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm text-slate-900"
                    />
                  </label>
                </div>
              </>
            )}

            <div className="mt-5 rounded-3xl border border-slate-200 bg-slate-50 p-5">
              <p className="text-sm font-semibold text-slate-800">Client-side schema check</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {headerRows.map((row) => (
                  <div
                    key={row.column}
                    className={`flex items-center gap-2 rounded-2xl border px-3 py-2 text-sm ${
                      row.present
                        ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                        : "border-rose-200 bg-rose-50 text-rose-700"
                    }`}
                  >
                    {row.present ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                    <span>{row.column}</span>
                  </div>
                ))}
              </div>
              {headerValidation.missing.length > 0 && (
                <p className="mt-4 text-sm text-rose-700">
                  Add these columns to your CSV and try again: {headerValidation.missing.join(", ")}
                </p>
              )}
              {headerValidation.allHeaders.length > 0 && headerValidation.missing.length === 0 && (
                <p className="mt-4 text-sm text-emerald-700">All required columns are present.</p>
              )}
            </div>
          </section>

          <CSVUploader
            onUpload={handleUpload}
            onFileSelected={handleFileSelected}
            uploading={uploading}
            domainLabel={selectedTemplate?.display_name || "dataset"}
            expectedColumns={parseCsvList(requiredColumns)}
          />

          {privacySummary && (
            <section className="section-card border border-emerald-200 bg-emerald-50/60">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-emerald-700">Privacy Shield</p>
              <h3 className="mt-2 text-2xl font-bold text-slate-900">Local PII hashing applied before upload</h3>
              <p className="mt-3 text-sm leading-7 text-slate-700">
                Rows processed: <span className="font-semibold">{privacySummary.rowsProcessed}</span> • Fields hashed:{" "}
                <span className="font-semibold">{privacySummary.fieldsHashed}</span>
              </p>
            </section>
          )}

          <LocalWasmPrecheckCard result={localPrecheck} proxyColumn={proxyColumn} />
        </>
      )}

      {!report && step === 2 && (
        <div className="section-card text-center">
          <h2 className="text-2xl font-bold text-slate-900">Waiting for a dataset</h2>
          <p className="mt-3 text-sm leading-7 text-slate-500">
            Select a CSV and start upload to generate fairness metrics and mitigation-ready insights.
          </p>
        </div>
      )}

      {report && (
        <>
          {report?.summary?.auto_detected_domain && (
            <section className="section-card border border-blue-200 bg-blue-50 text-blue-800">
              We detected this looks like a {report?.summary?.domain_label || "preset"} dataset. Using the{" "}
              {report?.summary?.domain_label || "selected"} preset.
            </section>
          )}
          <FairnessReportCard metrics={report.metrics} />
          <div className="rounded-xl border border-slate-200 bg-white p-6 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-xl">✨</span>
              <div>
                <p className="text-xs font-semibold text-amber-600 tracking-widest uppercase">
                  AI Fairness Verdict
                </p>
                <h3 className="text-lg font-bold text-slate-900">
                  Gemini Analysis
                  {geminiData?.source === "gemini-1.5-flash" && (
                    <span className="ml-2 text-xs font-normal text-green-600 bg-green-50 px-2 py-0.5 rounded-full border border-green-200">
                      Powered by Gemini
                    </span>
                  )}
                </h3>
              </div>
              <span className={`ml-auto text-xs font-semibold px-3 py-1 rounded-full border ${
                  geminiData?.risk_level === "high"
                    ? "bg-red-100 text-red-700 border-red-200"
                    : geminiData?.risk_level === "low"
                    ? "bg-green-100 text-green-700 border-green-200"
                    : "bg-amber-100 text-amber-700 border-amber-200"
                }`}>
                {geminiData?.risk_level === "high" 
                  ? "High Risk" 
                  : geminiData?.risk_level === "low"
                  ? "Low Risk"
                  : "Medium Risk"}
              </span>
            </div>

            {geminiLoading ? (
              <div className="space-y-2">
                <div className="h-3 bg-slate-100 rounded animate-pulse w-full"/>
                <div className="h-3 bg-slate-100 rounded animate-pulse w-4/5"/>
                <div className="h-3 bg-slate-100 rounded animate-pulse w-full"/>
                <p className="text-slate-400 text-xs mt-2">
                  Generating Gemini analysis...
                </p>
              </div>
            ) : geminiData ? (
              <>
                <div className="text-slate-700 text-sm leading-relaxed mb-4 space-y-3">
                  {geminiData.summary
                    .split('\n\n')
                    .filter(p => p.trim())
                    .map((p, i) => (
                      <p key={i}>{p}</p>
                    ))
                  }
                </div>
                {geminiData.bottom_line && (
                  <div className="bg-slate-900 rounded-lg p-4 mb-4">
                    <p className="text-white font-semibold text-sm">
                      {geminiData.bottom_line}
                    </p>
                  </div>
                )}
                <button
                  onClick={() => {
                    const text = 
                      `${geminiData.summary}\n\n` +
                      `${geminiData.bottom_line}`;
                    navigator.clipboard.writeText(text);
                  }}
                  className="px-4 py-2 text-sm border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-700 transition-colors"
                >
                  Copy for stakeholders
                </button>
              </>
            ) : (
              <p className="text-slate-500 text-sm">
                Analysis unavailable. Check backend connection.
              </p>
            )}
          </div>

          <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
            <div className="section-card">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Summary</p>
              <h3 className="mt-2 text-2xl font-bold text-slate-900">Audit completed successfully</h3>
              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                  <p className="text-sm font-medium text-slate-500">Records analyzed</p>
                  <p className="mt-2 text-3xl font-extrabold text-slate-900">{report.summary.total_candidates}</p>
                </div>
                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                  <p className="text-sm font-medium text-slate-500">Bias flags found</p>
                  <p className="mt-2 text-3xl font-extrabold text-slate-900">{report.summary.bias_flags}</p>
                </div>
              </div>
            </div>

            <div className="section-card">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Next Actions</p>
              <h3 className="mt-2 text-2xl font-bold text-slate-900">Choose how to continue</h3>
              <div className="mt-6 grid gap-4 md:grid-cols-2">
                <button
                  type="button"
                  onClick={() => navigate(`/mitigate/${report.audit.id}`)}
                  className="rounded-3xl bg-navy p-6 text-left text-white transition hover:bg-navy-light"
                >
                  <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-light">Mitigation Center</p>
                  <h4 className="mt-3 text-2xl font-bold">Apply Mitigation</h4>
                </button>
                <button
                  type="button"
                  onClick={() => navigate(`/candidates/${report.audit.id}`)}
                  className="rounded-3xl border border-slate-200 bg-white p-6 text-left transition hover:border-amber/50 hover:bg-amber/5"
                >
                  <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-dark">Explorer</p>
                  <h4 className="mt-3 text-2xl font-bold text-slate-900">View Records</h4>
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default Audit;
