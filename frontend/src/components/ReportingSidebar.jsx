import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Briefcase,
  Target,
  Bell,
  Users,
  ChevronRight,
} from "lucide-react";
import { useRole } from "../context/RoleContext";

const managerLinks = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/jobs", label: "Jobs", icon: Briefcase },
  { to: "/goals", label: "Goals", icon: Target },
  { to: "/notifications", label: "Approvals", icon: Bell },
];

const employeeLinks = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/goals", label: "My Goals", icon: Target },
];

export default function Sidebar() {
  const { role, setRole, ROLES } = useRole();
  const links = role === ROLES.MANAGER ? managerLinks : employeeLinks;

  return (
    <aside className="w-60 min-h-screen bg-gray-900 border-r border-gray-800 flex flex-col">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-gray-800">
        <p className="text-xs text-gray-500 uppercase tracking-widest mb-1">Platform</p>
        <h1 className="text-white font-bold text-base leading-tight">
          AI Digital Employee
        </h1>
      </div>

      {/* Role switcher */}
      <div className="px-4 py-3 border-b border-gray-800">
        <p className="text-xs text-gray-500 mb-2">Viewing as</p>
        <div className="flex rounded-lg overflow-hidden border border-gray-700 text-xs font-medium">
          <button
            onClick={() => setRole(ROLES.MANAGER)}
            className={`flex-1 py-1.5 transition ${
              role === ROLES.MANAGER
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-white"
            }`}
          >
            Manager
          </button>
          <button
            onClick={() => setRole(ROLES.EMPLOYEE)}
            className={`flex-1 py-1.5 transition ${
              role === ROLES.EMPLOYEE
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-white"
            }`}
          >
            Employee
          </button>
        </div>
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                isActive
                  ? "bg-blue-600/20 text-blue-400"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            <span className="flex-1">{label}</span>
            <ChevronRight className="w-3 h-3 opacity-40" />
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-gray-800">
        <p className="text-xs text-gray-600">AI Digital Employee Platform</p>
      </div>
    </aside>
  );
}