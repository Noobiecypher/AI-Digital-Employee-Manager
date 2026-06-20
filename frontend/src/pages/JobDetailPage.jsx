import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Copy, Check, Loader2, Users, AlertTriangle } from "lucide-react";
import { MAIN_API } from "../config";

// Mock data — remove once Person 1's backend is ready
const MOCK_JOBS = {
  "job-001": {
    job_id: "job-001",
    role: "Backend Engineer",
    department: "Engineering",
    status: "open",
    created_date: "2026-06-01",
    applicant_count: 12,
    embed_script: `<script src="https://ai-platform.com/embed/job-001.js" data-job-id="job-001" async></script>`,
  },
  "job-002": {
    job_id: "job-002",
    role: "Sales Executive",
    department: "Sales",
    status: "open",
    created_date: "2026-06-05",
    applicant_count: 7,
    embed_script: `<script src="https://ai-platform.com/embed/job-002.js" data-job-id="job-002" async></script>`,
  },
  "job-003": {
    job_id: "job-003",
    role: "HR Coordinator",
    department: "Human Resources",
    status: "closed",
    created_date: "2026-05-20",
    applicant_count: 24,
    embed_script: `<script src="https://ai-platform.com/embed/job-003.js" data-job-id="job-003" async></script>`,
  },
};

const STATUS_STYLES = {
  open: "bg-emerald-500/10 text-emerald-400",
  closed: "bg-gray-500/10 text-gray-400",
  draft: "bg-amber-500/10 text-amber-400",
};

export default function JobDetailPage() {
  const { job_id } = useParams();
  const navigate = useNavigate();

  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [usingMock, setUsingMock] = useState(false);
  const [copied, setCopied] = useState(false);
  const [shortlisting, setShortlisting] = useState(false);
  const [shortlistDone, setShortlistDone] = useState(false);

  useEffect(() => {
    const fetchJob = async () => {
      try {
        const res = await fetch(`${MAIN_API}/jobs/${job_id}`);
        if (!res.ok) throw new Error("Not found");
        const data = await res.json();
        setJob(data);
      } catch {
        const mock = MOCK_JOBS[job_id];
        if (mock) {
          setJob(mock);
          setUsingMock(true);
        }
      } finally {
        setLoading(false);
      }
    };
    fetchJob();
  }, [job_id]);

  const handleCopy = () => {
    navigator.clipboard.writeText(job.embed_script);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCloseApplications = async () => {
    setShortlisting(true);
    try {
      // Person 1 defines this endpoint — update path if needed
      await fetch(`${MAIN_API}/jobs/${job_id}/shortlist`, { method: "POST" });
    } catch {
      // Backend not ready yet — simulate for now
      await new Promise((r) => setTimeout(r, 1200));
    } finally {
      setShortlisting(false);
      setShortlistDone(true);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="animate-spin text-blue-500 w-8 h-8" />
    </div>
  );

  if (!job) return (
    <div className="p-8 text-center text-gray-500">
      <p>Job not found.</p>
      <button onClick={() => navigate("/jobs")} className="mt-4 text-blue-400 text-sm hover:underline">
        Back to Jobs
      </button>
    </div>
  );

  return (
    <div className="p-8 max-w-4xl">
      {/* Back */}
      <button
        onClick={() => navigate("/jobs")}
        className="flex items-center gap-2 text-gray-400 hover:text-white text-sm mb-6 transition"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Jobs
      </button>

      {/* Header */}
      <div className="flex justify-between items-start border-b border-gray-800 pb-6 mb-8">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-3xl font-bold text-white">{job.role}</h1>
            <span className={`px-2 py-0.5 rounded text-xs font-semibold capitalize ${STATUS_STYLES[job.status] || "bg-gray-700 text-gray-300"}`}>
              {job.status}
            </span>
          </div>
          <p className="text-gray-400 text-sm">{job.department} · Created {job.created_date}</p>
          {usingMock && (
            <p className="flex items-center gap-1 text-xs text-amber-400 mt-2">
              <AlertTriangle className="w-3 h-3" /> Using mock data
            </p>
          )}
        </div>

        {/* Applicant count */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl px-5 py-4 text-center">
          <Users className="w-5 h-5 text-blue-400 mx-auto mb-1" />
          <p className="text-2xl font-bold text-white">{job.applicant_count ?? 0}</p>
          <p className="text-xs text-gray-400 mt-0.5">Applicants</p>
        </div>
      </div>

      {/* Embed Script */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
        <div className="flex justify-between items-center mb-3">
          <div>
            <h2 className="text-white font-semibold">Embed Script</h2>
            <p className="text-gray-400 text-xs mt-0.5">Paste this into any webpage to embed the job application form</p>
          </div>
          <button
            onClick={handleCopy}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition ${
              copied
                ? "bg-emerald-600/20 text-emerald-400 border border-emerald-700"
                : "bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700"
            }`}
          >
            {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
        <div className="bg-gray-950 border border-gray-700 rounded-lg p-4 overflow-x-auto">
          <code className="text-sm text-blue-300 font-mono whitespace-pre">
            {job.embed_script || "No embed script generated yet. Run the recruitment agent to generate one."}
          </code>
        </div>
      </div>

      {/* Shortlisting trigger */}
      {job.status === "open" && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-white font-semibold mb-1">Shortlisting</h2>
          <p className="text-gray-400 text-sm mb-4">
            Close applications and trigger the Recruitment Agent to begin shortlisting candidates.
            Currently <span className="text-white font-medium">{job.applicant_count ?? 0}</span> applicants.
          </p>
          {shortlistDone ? (
            <div className="flex items-center gap-2 text-emerald-400 text-sm font-medium">
              <Check className="w-4 h-4" /> Shortlisting triggered successfully.
            </div>
          ) : (
            <button
              onClick={handleCloseApplications}
              disabled={shortlisting}
              className="flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition"
            >
              {shortlisting ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              {shortlisting ? "Triggering..." : "Close Applications & Run Shortlisting"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}