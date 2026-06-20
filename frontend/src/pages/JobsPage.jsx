import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Briefcase, Plus, ChevronRight, Loader2, AlertTriangle, X } from "lucide-react";
import { MAIN_API } from "../config";

const STATUS_STYLES = {
  open: "bg-emerald-500/10 text-emerald-400",
  closed: "bg-gray-500/10 text-gray-400",
  draft: "bg-amber-500/10 text-amber-400",
};

const MOCK_JOBS = [
  { job_id: "job-001", role: "Backend Engineer", department: "Engineering", status: "open", created_date: "2026-06-01", applicant_count: 12 },
  { job_id: "job-002", role: "Sales Executive", department: "Sales", status: "open", created_date: "2026-06-05", applicant_count: 7 },
  { job_id: "job-003", role: "HR Coordinator", department: "Human Resources", status: "closed", created_date: "2026-05-20", applicant_count: 24 },
];

function NewJobModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ role: "", department: "", status: "open" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async () => {
    if (!form.role.trim() || !form.department.trim()) {
      setError("Role and department are required.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${MAIN_API}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error("Failed to create job.");
      const created = await res.json();
      onCreated(created);
      onClose();
    } catch {
      // Backend not ready — create locally with mock id
      const mockCreated = {
        ...form,
        job_id: `job-${Date.now()}`,
        created_date: new Date().toISOString().slice(0, 10),
        applicant_count: 0,
      };
      onCreated(mockCreated);
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md p-6 shadow-xl">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-white font-semibold text-lg">New Job Posting</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider">Role *</label>
            <input
              type="text"
              placeholder="e.g. Backend Engineer"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider">Department *</label>
            <input
              type="text"
              placeholder="e.g. Engineering"
              value={form.department}
              onChange={(e) => setForm({ ...form, department: e.target.value })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider">Status</label>
            <select
              value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 transition"
            >
              <option value="open">Open</option>
              <option value="draft">Draft</option>
              <option value="closed">Closed</option>
            </select>
          </div>

          {error && <p className="text-red-400 text-xs">{error}</p>}
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm text-gray-300 rounded-lg transition"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-sm text-white font-medium rounded-lg transition"
          >
            {submitting ? "Creating..." : "Create Job"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const res = await fetch(`${MAIN_API}/jobs`);
        if (!res.ok) throw new Error("Failed to fetch jobs.");
        const data = await res.json();
        setJobs(data);
      } catch (err) {
        console.warn("Backend unavailable, using mock data.", err.message);
        setJobs(MOCK_JOBS);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchJobs();
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="animate-spin text-blue-500 w-8 h-8" />
    </div>
  );

  return (
    <div className="p-8">
      {showModal && (
        <NewJobModal
          onClose={() => setShowModal(false)}
          onCreated={(newJob) => setJobs((prev) => [newJob, ...prev])}
        />
      )}

      <header className="mb-8 flex justify-between items-center border-b border-gray-800 pb-5">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white">Job Postings</h1>
          <p className="text-gray-400 mt-1">Click a job to view its embed script</p>
        </div>
        <div className="flex items-center gap-3">
          {error && (
            <span className="flex items-center gap-1 text-xs text-amber-400">
              <AlertTriangle className="w-3 h-3" /> Using mock data
            </span>
          )}
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-sm font-medium rounded-lg transition"
          >
            <Plus className="w-4 h-4" /> New Job
          </button>
        </div>
      </header>

      {jobs.length === 0 ? (
        <div className="text-center py-24 text-gray-500">
          <Briefcase className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No job postings yet.</p>
        </div>
      ) : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 font-medium text-xs uppercase tracking-wider">
                <th className="px-6 py-4">Role</th>
                <th className="px-6 py-4">Department</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Applicants</th>
                <th className="px-6 py-4">Created</th>
                <th className="px-6 py-4"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {jobs.map((job) => (
                <tr
                  key={job.job_id}
                  onClick={() => navigate(`/jobs/${job.job_id}`)}
                  className="text-gray-300 hover:bg-gray-800/60 cursor-pointer transition"
                >
                  <td className="px-6 py-4 font-medium text-white">{job.role}</td>
                  <td className="px-6 py-4 text-gray-400">{job.department}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-0.5 rounded text-xs font-semibold capitalize ${STATUS_STYLES[job.status] || "bg-gray-700 text-gray-300"}`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-400">{job.applicant_count ?? "—"}</td>
                  <td className="px-6 py-4 text-gray-400">{job.created_date}</td>
                  <td className="px-6 py-4 text-right">
                    <ChevronRight className="w-4 h-4 text-gray-600 inline" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}