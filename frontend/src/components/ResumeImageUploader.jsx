import { useState } from "react";
import toast from "react-hot-toast";

function ResumeImageUploader() {
  const [files, setFiles] = useState([]);
  const [previewing, setPreviewing] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer?.files || []).filter(
      (f) => f.type === "application/pdf" || f.type.startsWith("image/")
    );
    if (dropped.length === 0) {
      toast.error("Only PDF or image files are supported.");
      return;
    }
    if (files.length + dropped.length > 50) {
      toast.error("Maximum 50 files allowed.");
      return;
    }
    setFiles((prev) => [...prev, ...dropped]);
  };

  const handleFileInput = (e) => {
    const selected = Array.from(e.target.files || []).filter(
      (f) => f.type === "application/pdf" || f.type.startsWith("image/")
    );
    if (files.length + selected.length > 50) {
      toast.error("Maximum 50 files allowed.");
      return;
    }
    setFiles((prev) => [...prev, ...selected]);
  };

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div>
      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-amber-300 bg-amber-50/40 px-6 py-10 text-center transition hover:border-amber-400 hover:bg-amber-50/60"
      >
        <p className="text-sm font-semibold text-slate-700">
          Drag & drop resume PDFs or images here
        </p>
        <p className="mt-1 text-xs text-slate-500">Up to 50 files • PDF, PNG, JPG</p>
        <label className="mt-4 cursor-pointer rounded-xl bg-amber-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-amber-600">
          Browse Files
          <input
            type="file"
            multiple
            accept=".pdf,image/*"
            onChange={handleFileInput}
            className="hidden"
          />
        </label>
      </div>

      {files.length > 0 && (
        <div className="mt-4">
          <p className="text-sm font-semibold text-slate-700 mb-2">
            {files.length} file{files.length !== 1 ? "s" : ""} selected
          </p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
              >
                <span className="truncate text-slate-700 max-w-[180px]">{file.name}</span>
                <button
                  type="button"
                  onClick={() => removeFile(index)}
                  className="ml-2 text-xs text-red-500 hover:text-red-700"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-slate-400 italic">
            Resume extraction via Gemini is coming soon. For now, please use the CSV upload below.
          </p>
        </div>
      )}
    </div>
  );
}

export default ResumeImageUploader;
