import { useState, useRef } from "react";

const ACCEPTED_TYPES = [
  "image/jpeg",
  "image/png", 
  "application/pdf"
];

const FIELD_LABELS = {
  age: "Age",
  gender: "Gender",
  education_tier: "Education Tier",
  years_experience: "Years Experience",
};

const TIER_COLORS = {
  "Tier 1": "bg-emerald-100 text-emerald-800 border-emerald-200",
  "Tier 2": "bg-blue-100 text-blue-800 border-blue-200",
  "Tier 3": "bg-amber-100 text-amber-800 border-amber-200",
  "Unknown": "bg-slate-100 text-slate-600 border-slate-200",
};

const GENDER_COLORS = {
  "Male": "bg-blue-100 text-blue-800 border-blue-200",
  "Female": "bg-pink-100 text-pink-800 border-pink-200",
  "Unknown": "bg-slate-100 text-slate-600 border-slate-200",
};

export default function ResumeImageUploader({ 
  onExtracted 
}) {
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [preview, setPreview] = useState(null);
  const inputRef = useRef(null);

  const handleFile = async (file) => {
    if (!file) return;
    
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setError(
        "Only JPEG, PNG, and PDF files are supported."
      );
      return;
    }

    setError(null);
    setResult(null);
    setLoading(true);

    if (file.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target.result);
      reader.readAsDataURL(file);
    } else {
      setPreview(null);
    }

    try {
      const token = 
        localStorage.getItem("token") ||
        localStorage.getItem("access_token");

      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        "http://localhost:8000/api/v1/extract-candidate",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        }
      );

      if (!response.ok) {
        const err = await response.json();
        throw new Error(
          err?.detail?.message || 
          "Extraction failed. Try a clearer image."
        );
      }

      const data = await response.json();
      setResult(data);
      if (onExtracted) onExtracted(data);

    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = () => setDragging(false);

  const handleInputChange = (e) => {
    handleFile(e.target.files[0]);
  };

  return (
    <div className="space-y-4">
      
      {/* Drop Zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
        className={`
          relative cursor-pointer rounded-3xl border-2 
          border-dashed p-10 text-center transition-all
          ${dragging 
            ? "border-amber-400 bg-amber-50" 
            : "border-slate-300 bg-slate-50 hover:border-amber-300 hover:bg-amber-50/50"
          }
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.pdf"
          className="hidden"
          onChange={handleInputChange}
        />

        <div className="flex flex-col items-center gap-3">
          <div className="rounded-2xl bg-amber-100 p-4">
            <svg 
              className="h-8 w-8 text-amber-600" 
              fill="none" 
              viewBox="0 0 24 24" 
              stroke="currentColor"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={1.5} 
                d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" 
              />
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={1.5} 
                d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" 
              />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">
              Drop resume photo or click to browse
            </p>
            <p className="mt-1 text-xs text-slate-500">
              JPEG, PNG, or PDF • Max 10MB
            </p>
            <p className="mt-2 text-xs font-semibold 
              text-amber-600 uppercase tracking-widest">
              Powered by Gemini 2.5 Pro
            </p>
          </div>
        </div>
      </div>

      {/* Image Preview */}
      {preview && (
        <div className="rounded-2xl overflow-hidden 
          border border-slate-200 max-h-48">
          <img 
            src={preview} 
            alt="Resume preview" 
            className="w-full object-cover"
          />
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="rounded-2xl border border-amber-200 
          bg-amber-50 p-6 text-center">
          <div className="flex items-center 
            justify-center gap-3">
            <div className="h-5 w-5 animate-spin 
              rounded-full border-2 border-amber-400 
              border-t-transparent"/>
            <p className="text-sm font-semibold 
              text-amber-700">
              Gemini 2.5 Pro is reading the document...
            </p>
          </div>
          <p className="mt-2 text-xs text-amber-600">
            Extracting age, gender, education, 
            and experience
          </p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="rounded-2xl border 
          border-red-200 bg-red-50 p-4">
          <p className="text-sm font-semibold 
            text-red-700">
            ⚠ {error}
          </p>
        </div>
      )}

      {/* Result Card */}
      {result && (
        <div className="rounded-2xl border 
          border-slate-200 bg-white p-6">
          <div className="flex items-center 
            gap-2 mb-4">
            <span className="text-lg">✨</span>
            <div>
              <p className="text-xs font-semibold 
                text-amber-600 tracking-widest uppercase">
                Extracted by Gemini 2.5 Pro
              </p>
              <h3 className="text-base font-bold 
                text-slate-900">
                Candidate Profile
              </h3>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            
            <div className="rounded-xl border 
              border-slate-100 bg-slate-50 p-3">
              <p className="text-xs text-slate-500 
                font-medium">Age</p>
              <p className="text-2xl font-bold 
                text-slate-900 mt-1">
                {result.age > 0 ? result.age : "—"}
              </p>
            </div>

            <div className="rounded-xl border 
              border-slate-100 bg-slate-50 p-3">
              <p className="text-xs text-slate-500 
                font-medium">Experience</p>
              <p className="text-2xl font-bold 
                text-slate-900 mt-1">
                {result.years_experience > 0 
                  ? `${result.years_experience}y` 
                  : "—"}
              </p>
            </div>

            <div className={`rounded-xl border p-3
              ${GENDER_COLORS[result.gender] || GENDER_COLORS["Unknown"]}`}>
              <p className="text-xs font-medium 
                opacity-70">Gender</p>
              <p className="text-base font-bold mt-1">
                {result.gender}
              </p>
            </div>

            <div className={`rounded-xl border p-3 
              ${TIER_COLORS[result.education_tier] || TIER_COLORS["Unknown"]}`}>
              <p className="text-xs font-medium 
                opacity-70">Education</p>
              <p className="text-base font-bold mt-1">
                {result.education_tier}
              </p>
            </div>

          </div>

          <div className="mt-4 rounded-xl 
            bg-slate-900 p-3 text-center">
            <p className="text-xs text-slate-400">
              This data feeds directly into the 
              FairFlow bias detection pipeline
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
