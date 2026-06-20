import { useState, useEffect } from "react";
import { Check, X, Clock, Bell, Loader2, AlertTriangle } from "lucide-react";
import { MAIN_API } from "../config";
import { useRole } from "../context/RoleContext";

const MOCK_NOTIFICATIONS = [
  {
    id: "n-001",
    type: "goal_completion",
    employee: "Raj Kumar",
    period: "Q2 2026",
    goal: "Reduce latency by 20%",
    comment: "Latency dropped 200ms to 150ms, PR #234",
    submitted_at: "2026-06-10",
    status: "pending",
  },
  {
    id: "n-002",
    type: "goal_completion",
    employee: "Priya Sharma",
    period: "Q2 2026",
    goal: "Launch sales campaign",
    comment: "Campaign went live on June 8, results in attached doc.",
    submitted_at: "2026-06-12",
    status: "pending",
  },
  {
    id: "n-003",
    type: "goal_completion",
    employee: "Ankit Verma",
    period: "Q2 2026",
    goal: "Onboard 3 new clients",
    comment: "Clients: Acme Corp, TechFlow, NovaSoft — all signed.",
    submitted_at: "2026-06-15",
    status: "approved",
  },
];

function NotificationCard({ item, onDecision, deciding }) {
  const isPending = item.status === "pending";

  return (
    <div className={`bg-gray-900 border rounded-xl p-5 transition ${
      isPending ? "border-gray-700" : "border-gray-800 opacity-60"
    }`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-semibold text-blue-400 uppercase tracking-wider">
              Goal Completion
            </span>
            <span className={`px-2 py-0.5 rounded text-xs font-semibold capitalize ${
              item.status === "pending"  ? "bg-amber-500/10 text-amber-400" :
              item.status === "approved" ? "bg-emerald-500/10 text-emerald-400" :
              "bg-red-500/10 text-red-400"
            }`}>
              {item.status}
            </span>
          </div>

          {/* Goal */}
          <p className="text-white font-medium text-sm mb-1">{item.goal}</p>
          <p className="text-gray-400 text-xs mb-3">
            {item.employee} · {item.period}
          </p>

          {/* Comment */}
          {item.comment && (
            <div className="bg-gray-800 rounded-lg px-3 py-2 text-xs text-gray-300 italic mb-3">
              "{item.comment}"
            </div>
          )}

          {/* Timestamp */}
          <p className="flex items-center gap-1 text-xs text-gray-500">
            <Clock className="w-3 h-3" /> Submitted {item.submitted_at}
          </p>
        </div>

        {/* Actions */}
        {isPending && (
          <div className="flex flex-col gap-2 shrink-0">
            <button
              onClick={() => onDecision(item, "approve")}
              disabled={!!deciding}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-400 text-xs font-medium rounded-lg transition disabled:opacity-50"
            >
              {deciding === item.id + "approve"
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <Check className="w-3.5 h-3.5" />}
              Approve
            </button>
            <button
              onClick={() => onDecision(item, "reject")}
              disabled={!!deciding}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600/20 hover:bg-red-600/40 text-red-400 text-xs font-medium rounded-lg transition disabled:opacity-50"
            >
              <X className="w-3.5 h-3.5" /> Reject
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function NotificationsPage() {
  const { role, ROLES } = useRole();
  const isManager = role === ROLES.MANAGER;

  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading]             = useState(true);
  const [usingMock, setUsingMock]         = useState(false);
  const [deciding, setDeciding]           = useState(null);
  const [filter, setFilter]               = useState("pending");

  useEffect(() => {
    const fetchNotifications = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${MAIN_API}/notifications`);
        if (!res.ok) throw new Error();
        const data = await res.json();
        setNotifications(data);
      } catch {
        setNotifications(MOCK_NOTIFICATIONS);
        setUsingMock(true);
      } finally {
        setLoading(false);
      }
    };
    fetchNotifications();
  }, []);

  const handleDecision = async (item, decision) => {
    setDeciding(item.id + decision);
    try {
      await fetch(`${MAIN_API}/goals/${item.employee}/${item.period}/approve`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: item.goal, decision }),
      });
    } catch {
      // Backend not ready — update locally
    } finally {
      setDeciding(null);
      setNotifications((prev) =>
        prev.map((n) =>
          n.id === item.id ? { ...n, status: decision === "approve" ? "approved" : "rejected" } : n
        )
      );
    }
  };

  const filtered = filter === "all"
    ? notifications
    : notifications.filter((n) => n.status === filter);

  const pendingCount = notifications.filter((n) => n.status === "pending").length;

  if (!isManager) return (
    <div className="p-8 text-center text-gray-500">
      <Bell className="w-10 h-10 mx-auto mb-3 opacity-30" />
      <p className="text-sm">Notifications are only visible to managers.</p>
    </div>
  );

  return (
    <div className="p-8 max-w-3xl">
      <header className="mb-8 border-b border-gray-800 pb-5 flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight text-white">Approvals</h1>
            {pendingCount > 0 && (
              <span className="px-2 py-0.5 rounded-full bg-blue-600 text-white text-xs font-bold">
                {pendingCount}
              </span>
            )}
          </div>
          <p className="text-gray-400 mt-1">Goal completion requests from employees</p>
        </div>
        {usingMock && (
          <span className="flex items-center gap-1 text-xs text-amber-400 mt-1">
            <AlertTriangle className="w-3 h-3" /> Using mock data
          </span>
        )}
      </header>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-6 bg-gray-900 border border-gray-800 rounded-lg p-1 w-fit">
        {["pending", "approved", "rejected", "all"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-md text-sm font-medium capitalize transition ${
              filter === f ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-blue-500 w-6 h-6" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <Bell className="w-8 h-8 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No {filter === "all" ? "" : filter} notifications.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filtered.map((item) => (
            <NotificationCard
              key={item.id}
              item={item}
              onDecision={handleDecision}
              deciding={deciding}
            />
          ))}
        </div>
      )}
    </div>
  );
}