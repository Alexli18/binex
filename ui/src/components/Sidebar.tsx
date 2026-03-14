import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  FileCode,
  Workflow,
  Wand2,
  LayoutDashboard,
  GitCompare,
  GitBranch,
  Bug,
  Stethoscope,
  Clock,
  Network,
  DollarSign,
  Wallet,
  Download,
  HeartPulse,
  Puzzle,
  Radio,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";

interface NavItem {
  label: string;
  path: string;
  icon: LucideIcon;
}

interface NavGroup {
  label: string;
  items: NavItem[];
  /** If true, group is only shown when a run is selected */
  requiresRunId?: boolean;
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Workflows",
    items: [
      { label: "Browse", path: "/workflows", icon: FileCode },
      { label: "Editor", path: "/editor", icon: Workflow },
      { label: "Scaffold", path: "/scaffold", icon: Wand2 },
    ],
  },
  {
    label: "Runs",
    items: [
      { label: "Dashboard", path: "/", icon: LayoutDashboard },
      { label: "Compare", path: "/diff", icon: GitCompare },
      { label: "Bisect", path: "/bisect", icon: GitBranch },
    ],
  },
  {
    label: "Analysis",
    requiresRunId: true,
    items: [
      { label: "Debug", path: "/debug", icon: Bug },
      { label: "Diagnose", path: "/diagnose", icon: Stethoscope },
      { label: "Trace", path: "/trace", icon: Clock },
      { label: "Lineage", path: "/lineage", icon: Network },
    ],
  },
  {
    label: "Costs & Budget",
    items: [
      { label: "Cost Dashboard", path: "/costs", icon: DollarSign },
      { label: "Budget", path: "/costs/budget", icon: Wallet },
    ],
  },
  {
    label: "Export",
    items: [{ label: "Export Runs", path: "/export", icon: Download }],
  },
  {
    label: "System",
    items: [
      { label: "Doctor", path: "/system/doctor", icon: HeartPulse },
      { label: "Plugins", path: "/system/plugins", icon: Puzzle },
      { label: "Gateway", path: "/system/gateway", icon: Radio },
    ],
  },
];

function NavGroupSection({
  group,
  collapsed,
  runId,
}: {
  group: NavGroup;
  collapsed: boolean;
  runId?: string;
}) {
  const [expanded, setExpanded] = useState(true);

  if (group.requiresRunId && !runId) {
    return null;
  }

  const resolvedItems = group.items.map((item) => {
    if (group.requiresRunId && runId) {
      return { ...item, path: `/runs/${runId}${item.path}` };
    }
    return item;
  });

  return (
    <div className="mb-2">
      {!collapsed && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex w-full items-center justify-between px-4 py-1.5 text-xs font-medium uppercase tracking-wider text-slate-500 hover:text-slate-400 transition-colors"
        >
          <span>{group.label}</span>
          <ChevronDown
            size={14}
            className={`transition-transform duration-200 ${
              expanded ? "" : "-rotate-90"
            }`}
          />
        </button>
      )}

      {(collapsed || expanded) && (
        <ul className="space-y-0.5">
          {resolvedItems.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                end={item.path === "/"}
                title={collapsed ? item.label : undefined}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-2 text-sm transition-colors ${
                    collapsed ? "justify-center px-0" : ""
                  } ${
                    isActive
                      ? "border-l-2 border-blue-500 bg-blue-600/20 text-blue-400"
                      : "border-l-2 border-transparent text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                  }`
                }
              >
                <item.icon size={18} className="shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const runIdMatch = location.pathname.match(/\/runs\/([^/]+)/);
  const runId = runIdMatch ? runIdMatch[1] : undefined;

  return (
    <aside
      className={`flex h-screen flex-col border-r border-slate-800 bg-slate-950 transition-all duration-200 ${
        collapsed ? "w-12" : "w-60"
      }`}
    >
      {/* Header / collapse toggle */}
      <div
        className={`flex items-center border-b border-slate-800 px-3 py-3 ${
          collapsed ? "justify-center" : "justify-between"
        }`}
      >
        {!collapsed && (
          <span className="text-sm font-semibold text-slate-200">Binex</span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3">
        {NAV_GROUPS.map((group) => (
          <NavGroupSection
            key={group.label}
            group={group}
            collapsed={collapsed}
            runId={runId}
          />
        ))}
      </nav>
    </aside>
  );
}
