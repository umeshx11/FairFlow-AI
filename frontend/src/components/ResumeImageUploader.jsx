import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  PlayCircle,
  Trash2,
  UploadCloud,
  XCircle
} from "lucide-react";
import { useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";
import { useNavigate } from "react-router-dom";

import {
  LAST_AUDIT_STORAGE_KEY,
  extractCandidateFromResume,
  uploadResumesAudit
} from "../api/fairlensApi";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "application/pdf"];
const MAX_FILES = 50;
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
const MIN_RECOMMENDED_CANDIDATES = 30;

const CSV_COLUMNS = [
  "name",
  "gender",
  "age",
  "ethnicity",
  "years_experience",
  "education_level",
  "hired",
  "skills",
  "previous_companies",
  "caste",
  "religion",
  "disability_status",
  "region"
];

const EDITABLE_FIELDS = [
  { key: "name", label: "Name", type: "text" },
  { key: "gender", label: "Gender", type: "select", options: ["Male", "Female", "Unknown"] },
  { key: "age", label: "Age", type: "number" },
  { key: "ethnicity", label: "Ethnicity", type: "text" },
  { key: "years_experience", label: "Experience", type: "number", step: "0.1" },
  {
    key: "education_level",
    label: "Education",
    type: "select",
    options: ["Tier 1", "Tier 2", "Tier 3", "Unknown"]
  },
  { key: "skills", label: "Skills", type: "text" },
  { key: "previous_companies", label: "Companies", type: "text" },
  { key: "caste", label: "Caste", type: "text" },
  { key: "religion", label: "Religion", type: "text" },
  { key: "disability_status", label: "Disability", type: "text" },
  { key: "region", label: "Region", type: "text" }
];

const emptyCandidate = (fileName = "") => ({
  name: fileName.replace(/\.[^.]+$/, "") || "Unknown",
  gender: "Unknown",
  age: 0,
  ethnicity: "Unknown",
  years_experience: 0,
  education_level: "Unknown",
  hired: null,
  skills: "",
  previous_companies: "",
  caste: "Unknown",
  religion: "Unknown",
  disability_status: "Unknown",
  region: "Unknown"
});

const formatSize = (bytes) => {
  if (!bytes) return "0 KB";
  const mb = bytes / 1024 / 1024;
  return mb >= 1 ? `${mb.toFixed(2)} MB` : `${(bytes / 1024).toFixed(1)} KB`;
};

const getErrorMessage = (err, fallback) => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return err?.message || fallback;
};

const csvEscape = (value) => {
  const normalized = value === null || value === undefined ? "" : String(value);
  if (/[",\n\r]/.test(normalized)) {
    return `"${normalized.replace(/"/g, '""')}"`;
  }
  return normalized;
};

export default function ResumeImageUploader() {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [rows, setRows] = useState([]);
  const [extracting, setExtracting] = useState(false);
  const [extractProgress, setExtractProgress] = useState({ done: 0, total: 0 });
  const [runningAudit, setRunningAudit] = useState(false);
  const [error, setError] = useState("");

  const allHiredSet = rows.length > 0 && rows.every((row) => row.hired === 0 || row.hired === 1);
  const showLowSampleWarning = rows.length > 0 && rows.length < MIN_RECOMMENDED_CANDIDATES;
  const failedCount = useMemo(() => rows.filter((row) => row.status === "failed").length, [rows]);

  const updateRow = (id, key, value) => {
    setRows((current) =>
      current.map((row) => {
        if (row.id !== id) return row;
        const nextValue =
          key === "age" ? Math.max(0, Number(value) || 0) :
          key === "years_experience" ? Math.max(0, Number(value) || 0) :
          value;
        return { ...row, [key]: nextValue };
      })
    );
  };

  const removeRow = (id) => {
    setRows((current) => current.filter((row) => row.id !== id));
  };

  const validateFiles = (selectedFiles) => {
    if (rows.length + selectedFiles.length > MAX_FILES) {
      return `Upload up to ${MAX_FILES} resumes per batch. Delete rows before adding more.`;
    }
    const invalidType = selectedFiles.find((file) => !ACCEPTED_TYPES.includes(file.type));
    if (invalidType) {
      return `${invalidType.name} is not supported. Use PDF, JPEG, or PNG files.`;
    }
    const oversized = selectedFiles.find((file) => file.size > MAX_FILE_SIZE_BYTES);
    if (oversized) {
      return `${oversized.name} is ${formatSize(oversized.size)}. Each file must be 10MB or less.`;
    }
    return "";
  };

  const handleFiles = async (fileList) => {
    const selectedFiles = Array.from(fileList || []);
    if (!selectedFiles.length || extracting) return;

    const validationError = validateFiles(selectedFiles);
    if (validationError) {
      setError(validationError);
      return;
    }

    setError("");
    setExtracting(true);
    setExtractProgress({ done: 0, total: selectedFiles.length });

    for (let index = 0; index < selectedFiles.length; index += 1) {
      const file = selectedFiles[index];
      const rowId = `${Date.now()}-${index}-${file.name}`;
      const baseRow = {
        id: rowId,
        file_name: file.name,
        file_size: file.size,
        status: "extracting",
        error: "",
        ...emptyCandidate(file.name)
      };
      setRows((current) => [...current, baseRow]);

      try {
        const formData = new FormData();
        formData.append("file", file);
        const extracted = await extractCandidateFromResume(formData, { silent: true });
        setRows((current) =>
          current.map((row) =>
            row.id === rowId
              ? {
                  ...row,
                  ...emptyCandidate(file.name),
                  ...extracted,
                  hired: null,
                  status: "ready",
                  error: ""
                }
              : row
          )
        );
      } catch (err) {
        setRows((current) =>
          current.map((row) =>
            row.id === rowId
              ? {
                  ...row,
                  status: "failed",
                  error: getErrorMessage(err, "Extraction failed. Edit this row manually or delete it.")
                }
              : row
          )
        );
      } finally {
        setExtractProgress({ done: index + 1, total: selectedFiles.length });
      }
    }

    setExtracting(false);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  const downloadCsv = () => {
    const csvRows = [
      CSV_COLUMNS.join(","),
      ...rows.map((row) =>
        CSV_COLUMNS.map((column) => {
          if (column === "hired") return csvEscape(row.hired === 1 ? 1 : 0);
          return csvEscape(row[column]);
        }).join(",")
      )
    ];
    const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "resume_candidates.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const runBiasAudit = async () => {
    if (!allHiredSet) {
      setError("Set Hired? to Yes or No for every resume before running the audit.");
      return;
    }

    setRunningAudit(true);
    setError("");
    try {
      const candidates = rows.map((row) =>
        CSV_COLUMNS.reduce((payload, column) => {
          payload[column] = column === "hired" ? Number(row.hired) : row[column];
          return payload;
        }, {})
      );
      const response = await uploadResumesAudit(candidates);
      const auditId = response.audit_id || response.audit?.id;
      if (!auditId) {
        throw new Error("Audit completed but no audit id was returned.");
      }
      localStorage.setItem(LAST_AUDIT_STORAGE_KEY, auditId);
      toast.success(response.warning || "Resume audit completed.");
      navigate(`/candidates/${auditId}`);
    } catch (err) {
      setError(getErrorMessage(err, "Could not run the resume audit."));
    } finally {
      setRunningAudit(false);
    }
  };

  return (
    <div className="space-y-5">
      <div
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          handleFiles(event.dataTransfer.files);
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition ${
          dragging
            ? "border-amber-400 bg-amber-50"
            : "border-slate-300 bg-white hover:border-amber-300 hover:bg-amber-50/40"
        } ${extracting ? "pointer-events-none opacity-80" : ""}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.pdf"
          multiple
          className="hidden"
          onChange={(event) => handleFiles(event.target.files)}
        />
        <div className="mx-auto flex max-w-xl flex-col items-center gap-3">
          <div className="rounded-full bg-navy p-4 text-white">
            <UploadCloud className="h-7 w-7" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-slate-900">
              Upload resumes for a batch audit
            </h3>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Select up to 50 PDF, JPEG, or PNG resumes. Each file must be 10MB or less.
            </p>
          </div>
          <div className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Gemini extraction, editable before audit
          </div>
        </div>
      </div>

      {extracting && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-center gap-3 text-sm font-semibold text-amber-800">
            <Loader2 className="h-5 w-5 animate-spin" />
            Extracting resumes {extractProgress.done}/{extractProgress.total}
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <p className="text-sm font-medium">{error}</p>
        </div>
      )}

      {showLowSampleWarning && (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-800">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <p className="text-sm leading-6">
            Since fewer than 30 candidates are uploaded, the audit may not be fully accurate.
            You can still continue after setting every Hired? value.
          </p>
        </div>
      )}

      {rows.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white">
          <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-dark">
                Review extracted data
              </p>
              <h3 className="mt-1 text-xl font-bold text-slate-900">
                {rows.length} candidate{rows.length === 1 ? "" : "s"} ready for review
              </h3>
              {failedCount > 0 && (
                <p className="mt-1 text-sm text-red-600">
                  {failedCount} extraction{failedCount === 1 ? "" : "s"} failed. Edit red rows or delete them.
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={extracting || rows.length >= MAX_FILES}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-amber/60 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <UploadCloud className="h-4 w-4" />
              Add Files
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-[1500px] divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th className="px-3 py-3">File</th>
                  {EDITABLE_FIELDS.map((field) => (
                    <th key={field.key} className="px-3 py-3">
                      {field.label}
                    </th>
                  ))}
                  <th className="px-3 py-3">Hired?</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Delete</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row) => (
                  <tr key={row.id} className={row.status === "failed" ? "bg-red-50" : "bg-white"}>
                    <td className="max-w-[180px] px-3 py-3 align-top">
                      <div className="flex items-start gap-2">
                        <FileText className="mt-1 h-4 w-4 shrink-0 text-slate-400" />
                        <div>
                          <p className="truncate font-semibold text-slate-800">{row.file_name}</p>
                          <p className="text-xs text-slate-500">{formatSize(row.file_size)}</p>
                          {row.error && <p className="mt-1 text-xs text-red-600">{row.error}</p>}
                        </div>
                      </div>
                    </td>
                    {EDITABLE_FIELDS.map((field) => (
                      <td key={field.key} className="px-3 py-3 align-top">
                        {field.type === "select" ? (
                          <select
                            value={row[field.key] ?? "Unknown"}
                            onChange={(event) => updateRow(row.id, field.key, event.target.value)}
                            className="w-32 rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm text-slate-900"
                          >
                            {field.options.map((option) => (
                              <option key={option} value={option}>
                                {option}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <input
                            type={field.type}
                            step={field.step}
                            value={row[field.key] ?? ""}
                            onChange={(event) => updateRow(row.id, field.key, event.target.value)}
                            className="w-36 rounded-lg border border-slate-200 px-2 py-2 text-sm text-slate-900"
                          />
                        )}
                      </td>
                    ))}
                    <td className="px-3 py-3 align-top">
                      <div className="grid w-32 grid-cols-2 overflow-hidden rounded-lg border border-slate-200">
                        <button
                          type="button"
                          onClick={() => updateRow(row.id, "hired", 1)}
                          className={`px-3 py-2 text-xs font-bold transition ${
                            row.hired === 1
                              ? "bg-emerald-600 text-white"
                              : "bg-white text-slate-600 hover:bg-emerald-50"
                          }`}
                        >
                          Yes
                        </button>
                        <button
                          type="button"
                          onClick={() => updateRow(row.id, "hired", 0)}
                          className={`border-l border-slate-200 px-3 py-2 text-xs font-bold transition ${
                            row.hired === 0
                              ? "bg-red-600 text-white"
                              : "bg-white text-slate-600 hover:bg-red-50"
                          }`}
                        >
                          No
                        </button>
                      </div>
                    </td>
                    <td className="px-3 py-3 align-top">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold ${
                          row.status === "failed"
                            ? "border-red-200 bg-red-100 text-red-700"
                            : row.status === "extracting"
                              ? "border-amber-200 bg-amber-50 text-amber-700"
                              : "border-emerald-200 bg-emerald-50 text-emerald-700"
                        }`}
                      >
                        {row.status === "failed" ? (
                          <XCircle className="h-3.5 w-3.5" />
                        ) : row.status === "extracting" ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        )}
                        {row.status === "failed" ? "Needs edit" : row.status === "extracting" ? "Reading" : "Ready"}
                      </span>
                    </td>
                    <td className="px-3 py-3 align-top">
                      <button
                        type="button"
                        onClick={() => removeRow(row.id)}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600"
                        aria-label={`Delete ${row.file_name}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!allHiredSet && (
            <div className="border-t border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              Set Hired? to Yes or No for every row to unlock CSV download and bias audit.
            </div>
          )}
        </div>
      )}

      {allHiredSet && (
        <div className="flex flex-col gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-bold text-emerald-900">All hiring outcomes are set.</p>
            <p className="mt-1 text-sm text-emerald-800">
              Download the reviewed table or create a full FairFlow audit from these rows.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={downloadCsv}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-300 bg-white px-4 py-2 text-sm font-semibold text-emerald-800 transition hover:bg-emerald-100"
            >
              <Download className="h-4 w-4" />
              Download CSV
            </button>
            <button
              type="button"
              onClick={runBiasAudit}
              disabled={runningAudit}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-navy px-4 py-2 text-sm font-semibold text-white transition hover:bg-navy-light disabled:cursor-not-allowed disabled:opacity-60"
            >
              {runningAudit ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
              {runningAudit ? "Running Audit..." : "Run Bias Audit"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
