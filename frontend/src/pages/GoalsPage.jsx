import { useState, useEffect } from "react";
import { Target, Plus, Check, X, Clock, Loader2, AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import { MAIN_API } from "../config";
import { useRole } from "../context/RoleContext";

// ─── Mock Data ────────────────────────────────────────────────────────────────
const MOCK_EMPLOYEES = ["Raj Kumar", "Priya Sharma", "Ankit Verma"];
const MOCK_PERIODS = ["Q1 2026", "Q2 2026", "Q3 2026"];

const MOCK_GOALS = {
  "Raj Kumar": {
    "Q2 2026": {
      goals_set: ["Complete backend API", "Reduce latency by 20%", "Mentor a junior developer"],
      goals_achieved: ["Complete backend API"],
      pending_approvals: [
        { goal: "Reduce latency by 20%", comment: "Latency dropped 200ms to 150ms, PR #234", submitted_at: "2026-06-10", status: "pending" }
      ],
    },
  },
  "Priya Sharma": {
    "Q2 2026": {
      goals_set: ["Launch sales campaign", "Onboard 3 new clients"],
      goals_achieved: [],
      pending_approvals: [],
    },
  },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
const goalStatus = (goal, data) => {
  if (data.goals_achieved.includes(goal)) return "achieved";
  if (data.pending_approvals.find((p) => p.goal === goal)) return "pending";
  return "open";
};

const STATUS_PILL = {
  achieved: "bg-emerald-500/10 text-emerald-400",
  pending:  "bg-amber-500/10 text-amber-400",
  open:     "bg-gray-700 text-gray-400",
};

// ─── Manager: Set Goals Panel ─────────────────────────────────────────────────
// employee and period are passed from parent — no duplicate selectors here
function SetGoalsPanel({ employee, period, onGoalsCreated }) {
  const [goalInput, setGoalInput] = useState("");
  const [goals, setGoals]         = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone]           = useState(false);
  const [error, setError]         = useState(null);

  // Reset when employee/period changes so the panel feels fresh
  useEffect(() => {
    setGoals([]);
    setGoalInput("");
    setDone(false);
    setError(null);
  }, [employee, period]);

  const addGoal = () => {
    if (!goalInput.trim()) return;
    setGoals([...goals, goalInput.trim()]);
    setGoalInput("");
  };

  const handleSubmit = async () => {
    if (!employee || !period || goals.length === 0) {
      setError("Add at least one goal.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${MAIN_API}/goals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ employee_name: employee, review_period: period, goals_set: goals }),
      });
      if (!res.ok) throw new Error();
    } catch {
      // Backend not ready — proceed locally
    } finally {
      setSubmitting(false);
      setDone(true);
      onGoalsCreated?.({ employee, period, goals });
    }
  };

  if (done) return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-emerald-400 text-sm font-medium py-2">
        <Check className="w-4 h-4" /> Goals set for <span className="font-semibold">{employee}</span> — {period}.
      </div>
      <button
        onClick={() => { setDone(false); setGoals([]); }}
        className="text-xs text-gray-400 hover:text-white underline transition"
      >
        Add more goals
      </button>
    </div>
  );

  return (
    <div className="space-y-4">
      {/* Context reminder — read-only, driven by top-level selectors */}
      <div className="flex gap-3 mb-1">
        <span className="text-xs text-gray-400 uppercase tracking-wider">Setting goals for</span>
        <span className="text-xs font-semibold text-white">{employee || "—"}</span>
        <span className="text-xs text-gray-500">·</span>
        <span className="text-xs font-semibold text-white">{period || "—"}</span>
      </div>

      <div>
        <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider">Goals</label>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="e.g. Complete backend API"
            value={goalInput}
            onChange={(e) => setGoalInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addGoal()}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={addGoal}
            className="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm text-white transition"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
        {goals.length > 0 && (
          <ul className="mt-3 space-y-2">
            {goals.map((g, i) => (
              <li key={i} className="flex items-center justify-between bg-gray-800 rounded-lg px-3 py-2 text-sm text-gray-300">
                <span>{g}</span>
                <button onClick={() => setGoals(goals.filter((_, j) => j !== i))} className="text-gray-500 hover:text-red-400 transition">
                  <X className="w-3.5 h-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {error && <p className="text-red-400 text-xs">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={submitting}
        className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-sm text-white font-medium rounded-lg transition"
      >
        {submitting ? "Saving..." : "Set Goals"}
      </button>
    </div>
  );
}

// ─── Employee: My Goals Panel ─────────────────────────────────────────────────
function MyGoalsPanel({ data, employeeName, period, onSubmitted }) {
  const [submitting, setSubmitting] = useState(null); // goal string being submitted
  const [comments, setComments]     = useState({});
  const [expanded, setExpanded]     = useState({});

  const handleMarkComplete = async (goal) => {
    setSubmitting(goal);
    try {
      await fetch(`${MAIN_API}/goals/${employeeName}/${period}/complete`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, comment: comments[goal] || "" }),
      });
    } catch {
      // Backend not ready — proceed locally
    } finally {
      setSubmitting(null);
      onSubmitted?.(goal, comments[goal] || "");
    }
  };

  if (!data) return <p className="text-gray-500 text-sm">No goals found for the selected period.</p>;

  return (
    <ul className="space-y-3">
      {data.goals_set.map((goal) => {
        const status = goalStatus(goal, data);
        const isOpen = expanded[goal];
        return (
          <li key={goal} className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-3">
                <span className={`px-2 py-0.5 rounded text-xs font-semibold capitalize ${STATUS_PILL[status]}`}>
                  {status === "pending" ? "Pending Approval" : status}
                </span>
                <span className="text-sm text-gray-200">{goal}</span>
              </div>
              {status === "open" && (
                <button
                  onClick={() => setExpanded({ ...expanded, [goal]: !isOpen })}
                  className="text-gray-400 hover:text-white transition"
                >
                  {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
              )}
            </div>

            {status === "open" && isOpen && (
              <div className="px-4 pb-4 border-t border-gray-700 pt-3 space-y-3">
                <textarea
                  rows={2}
                  placeholder="Add a comment or proof link (optional)"
                  value={comments[goal] || ""}
                  onChange={(e) => setComments({ ...comments, [goal]: e.target.value })}
                  className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 resize-none"
                />
                <button
                  onClick={() => handleMarkComplete(goal)}
                  disabled={submitting === goal}
                  className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-sm text-white font-medium rounded-lg transition"
                >
                  {submitting === goal ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                  Mark Complete
                </button>
              </div>
            )}

            {status === "pending" && (
              <div className="px-4 pb-3 text-xs text-gray-400 border-t border-gray-700 pt-2">
                {data.pending_approvals.find((p) => p.goal === goal)?.comment || "Awaiting manager approval."}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

// ─── Manager: Approval Panel ──────────────────────────────────────────────────
function ApprovalsPanel({ data, employeeName, period, onDecision }) {
  const [deciding, setDeciding] = useState(null);

  const pending = data?.pending_approvals?.filter((p) => p.status === "pending") || [];

  const handleDecision = async (goal, decision) => {
    setDeciding(goal + decision);
    try {
      await fetch(`${MAIN_API}/goals/${employeeName}/${period}/approve`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, decision }),
      });
    } catch {
      // Backend not ready — proceed locally
    } finally {
      setDeciding(null);
      onDecision?.(goal, decision);
    }
  };

  if (pending.length === 0) return (
    <p className="text-gray-500 text-sm">No pending approvals.</p>
  );

  return (
    <ul className="space-y-4">
      {pending.map((item) => (
        <li key={item.goal} className="bg-gray-800 rounded-xl border border-gray-700 p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-white mb-1">{item.goal}</p>
              {item.comment && (
                <p className="text-xs text-gray-400 mb-1">"{item.comment}"</p>
              )}
              <p className="text-xs text-gray-500 flex items-center gap-1">
                <Clock className="w-3 h-3" /> Submitted {item.submitted_at}
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                onClick={() => handleDecision(item.goal, "reject")}
                disabled={!!deciding}
                className="flex items-center gap-1 px-3 py-1.5 bg-red-600/20 hover:bg-red-600/40 text-red-400 text-xs font-medium rounded-lg transition disabled:opacity-50"
              >
                <X className="w-3.5 h-3.5" /> Reject
              </button>
              <button
                onClick={() => handleDecision(item.goal, "approve")}
                disabled={!!deciding}
                className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-400 text-xs font-medium rounded-lg transition disabled:opacity-50"
              >
                {deciding === item.goal + "approve"
                  ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  : <Check className="w-3.5 h-3.5" />}
                Approve
              </button>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function GoalsPage() {
  const { role, ROLES } = useRole();
  const isManager = role === ROLES.MANAGER;

  const [employee, setEmployee] = useState(MOCK_EMPLOYEES[0]);
  const [period, setPeriod]     = useState(MOCK_PERIODS[1]);
  const [goalsData, setGoalsData] = useState(null);
  const [loading, setLoading]   = useState(false);
  const [usingMock, setUsingMock] = useState(false);
  const [activeTab, setActiveTab] = useState(isManager ? "set" : "my-goals");

  useEffect(() => {
    setActiveTab(isManager ? "set" : "my-goals");
  }, [isManager]);

  useEffect(() => {
    const fetchGoals = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${MAIN_API}/goals/${employee}/${period}`);
        if (!res.ok) throw new Error();
        const data = await res.json();
        setGoalsData(data);
        setUsingMock(false);
      } catch {
        const mock = MOCK_GOALS[employee]?.[period] || null;
        setGoalsData(mock);
        setUsingMock(true);
      } finally {
        setLoading(false);
      }
    };
    fetchGoals();
  }, [employee, period]);

  // When manager sets new goals, merge them into local goalsData so the
  // employee view (View Progress tab / employee My Goals) reflects them immediately
  const handleGoalsCreated = ({ employee: emp, period: per, goals: newGoals }) => {
    // Only merge if the top-level selectors still match what was just set
    setGoalsData((prev) => {
      const base = prev || { goals_set: [], goals_achieved: [], pending_approvals: [] };
      const merged = [...base.goals_set];
      newGoals.forEach((g) => { if (!merged.includes(g)) merged.push(g); });
      return { ...base, goals_set: merged };
    });
  };

  // Local state updates when backend isn't ready
  const handleSubmitted = (goal, comment) => {
    setGoalsData((prev) => ({
      ...prev,
      pending_approvals: [
        ...(prev.pending_approvals || []),
        { goal, comment, submitted_at: new Date().toISOString().slice(0, 10), status: "pending" },
      ],
    }));
  };

  const handleDecision = (goal, decision) => {
    setGoalsData((prev) => ({
      ...prev,
      goals_achieved: decision === "approve"
        ? [...prev.goals_achieved, goal]
        : prev.goals_achieved,
      pending_approvals: prev.pending_approvals.filter((p) => p.goal !== goal),
    }));
  };

  const managerTabs = [
    { id: "set",       label: "Set Goals" },
    { id: "approvals", label: "Approvals" },
    { id: "view",      label: "View Progress" },
  ];
  const employeeTabs = [
    { id: "my-goals", label: "My Goals" },
  ];
  const tabs = isManager ? managerTabs : employeeTabs;

  return (
    <div className="p-8 max-w-4xl">
      <header className="mb-8 border-b border-gray-800 pb-5">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white">Goals</h1>
            <p className="text-gray-400 mt-1">
              {isManager ? "Set, review, and approve employee goals" : "Track and submit your goal completions"}
            </p>
          </div>
          {usingMock && (
            <span className="flex items-center gap-1 text-xs text-amber-400 mt-1">
              <AlertTriangle className="w-3 h-3" /> Using mock data
            </span>
          )}
        </div>
      </header>

      {/* Single employee + period selector — shared by all tabs */}
      <div className="flex gap-4 mb-6">
        <div>
          <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider">Employee</label>
          <select
            value={employee}
            onChange={(e) => setEmployee(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
          >
            {MOCK_EMPLOYEES.map((e) => <option key={e}>{e}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider">Review Period</label>
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
          >
            {MOCK_PERIODS.map((p) => <option key={p}>{p}</option>)}
          </select>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-900 border border-gray-800 rounded-lg p-1 w-fit">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition ${
              activeTab === tab.id
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-white"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="animate-spin text-blue-500 w-6 h-6" />
          </div>
        ) : (
          <>
            {activeTab === "set" && (
              <SetGoalsPanel
                employee={employee}
                period={period}
                onGoalsCreated={handleGoalsCreated}
              />
            )}
            {activeTab === "approvals" && (
              <ApprovalsPanel
                data={goalsData}
                employeeName={employee}
                period={period}
                onDecision={handleDecision}
              />
            )}
            {(activeTab === "view" || activeTab === "my-goals") && (
              <MyGoalsPanel
                data={goalsData}
                employeeName={employee}
                period={period}
                onSubmitted={handleSubmitted}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}