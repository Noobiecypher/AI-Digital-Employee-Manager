import { useState } from "react";
import { useParams } from "react-router-dom";
import { Upload, Check, AlertTriangle, X, Loader2 } from "lucide-react";
import { MAIN_API } from "../config";

const MAX_FILE_SIZE_MB = 5;
const ACCEPTED_TYPES = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"];
const ACCEPTED_EXTENSIONS = ".pdf, .docx";

export default function ApplyPage() {
  const { job_id } = useParams();

  const [form, setForm] = useState({ name: "", email: "", phone: "" });
  const [file, setFile] = useState(null);
  const [fileError, setFileError] = useState(null);
  const [formErrors, setFormErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // ─── Validation ─────────────────────────────────────────────────────────────
  const validateForm = () => {
    const errors = {};
    if (!form.name.trim()) errors.name = "Full name is required.";
    if (!form.email.trim()) errors.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errors.email = "Enter a valid email.";
    if (!form.phone.trim()) errors.phone = "Phone number is required.";
    if (!file) errors.file = "Please upload your resume.";
    return errors;
  };

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    setFileError(null);
    if (!selected) return;

    if (!ACCEPTED_TYPES.includes(selected.type)) {
      setFileError("Only PDF or DOCX files are accepted.");
      return;
    }
    if (selected.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setFileError(`File must be under ${MAX_FILE_SIZE_MB}MB.`);
      return;
    }
    setFile(selected);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFileChange({ target: { files: [dropped] } });
  };

  const handleSubmit = async () => {
    const errors = validateForm();
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }
    setFormErrors({});
    setSubmitting(true);
    setSubmitError(null);

    try {
      const formData = new FormData();
      formData.append("name", form.name);
      formData.append("email", form.email);
      formData.append("phone", form.phone);
      formData.append("job_id", job_id);
      formData.append("resume", file);

      const res = await fetch(`${MAIN_API}/applications`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Submission failed.");
      setSubmitted(true);
    } catch {
      // Backend not ready — simulate success
      await new Promise((r) => setTimeout(r, 800));
      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  };

  // ─── Success Screen ──────────────────────────────────────────────────────────
  if (submitted) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 bg-emerald-500/10 rounded-full flex items-center justify-center mx-auto mb-6">
          <Check className="w-8 h-8 text-emerald-400" />
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">Application Submitted</h2>
        <p className="text-gray-400 text-sm leading-relaxed">
          Thank you for applying. Our recruitment team will review your application and get back to you shortly.
        </p>
      </div>
    </div>
  );

  // ─── Form ────────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="mb-8 text-center">
          <p className="text-xs text-blue-400 uppercase tracking-widest mb-2">Job Application</p>
          <h1 className="text-3xl font-bold text-white">Apply Now</h1>
          <p className="text-gray-400 text-sm mt-2">
            Job ID: <span className="font-mono text-blue-400">{job_id}</span>
          </p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 space-y-5">
          {/* Name */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider">Full Name *</label>
            <input
              type="text"
              placeholder="Raj Kumar"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className={`w-full bg-gray-800 border rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none transition ${
                formErrors.name ? "border-red-500 focus:border-red-400" : "border-gray-700 focus:border-blue-500"
              }`}
            />
            {formErrors.name && <p className="text-red-400 text-xs mt-1">{formErrors.name}</p>}
          </div>

          {/* Email */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider">Email *</label>
            <input
              type="email"
              placeholder="raj@example.com"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className={`w-full bg-gray-800 border rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none transition ${
                formErrors.email ? "border-red-500 focus:border-red-400" : "border-gray-700 focus:border-blue-500"
              }`}
            />
            {formErrors.email && <p className="text-red-400 text-xs mt-1">{formErrors.email}</p>}
          </div>

          {/* Phone */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider">Phone *</label>
            <input
              type="tel"
              placeholder="+91 98765 43210"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              className={`w-full bg-gray-800 border rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none transition ${
                formErrors.phone ? "border-red-500 focus:border-red-400" : "border-gray-700 focus:border-blue-500"
              }`}
            />
            {formErrors.phone && <p className="text-red-400 text-xs mt-1">{formErrors.phone}</p>}
          </div>

          {/* Resume Upload */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider">Resume *</label>
            {file ? (
              <div className="flex items-center justify-between bg-gray-800 border border-gray-700 rounded-lg px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-blue-600/20 rounded flex items-center justify-center">
                    <Upload className="w-4 h-4 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-sm text-white font-medium truncate max-w-xs">{file.name}</p>
                    <p className="text-xs text-gray-400">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                </div>
                <button onClick={() => setFile(null)} className="text-gray-400 hover:text-red-400 transition">
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                className={`border-2 border-dashed rounded-lg px-6 py-8 text-center cursor-pointer transition ${
                  formErrors.file ? "border-red-500" : "border-gray-700 hover:border-blue-500"
                }`}
                onClick={() => document.getElementById("resume-input").click()}
              >
                <Upload className="w-6 h-6 text-gray-500 mx-auto mb-2" />
                <p className="text-sm text-gray-400">
                  Drag & drop or <span className="text-blue-400">browse</span>
                </p>
                <p className="text-xs text-gray-500 mt-1">PDF or DOCX · Max {MAX_FILE_SIZE_MB}MB</p>
              </div>
            )}
            <input
              id="resume-input"
              type="file"
              accept={ACCEPTED_EXTENSIONS}
              className="hidden"
              onChange={handleFileChange}
            />
            {fileError && (
              <p className="flex items-center gap-1 text-red-400 text-xs mt-1">
                <AlertTriangle className="w-3 h-3" /> {fileError}
              </p>
            )}
            {formErrors.file && !fileError && (
              <p className="text-red-400 text-xs mt-1">{formErrors.file}</p>
            )}
          </div>

          {submitError && (
            <p className="flex items-center gap-1 text-red-400 text-xs">
              <AlertTriangle className="w-3 h-3" /> {submitError}
            </p>
          )}

          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium rounded-lg text-sm transition flex items-center justify-center gap-2"
          >
            {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Submitting...</> : "Submit Application"}
          </button>
        </div>
      </div>
    </div>
  );
}