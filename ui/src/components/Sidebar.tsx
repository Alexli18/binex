import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  Workflow,
  Wand2,
  LayoutDashboard,
  HeartPulse,
  Puzzle,
  Radio,
  GitCompare,
  GitBranch,
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
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Build",
    items: [
      { label: "Editor", path: "/editor", icon: Workflow },
      { label: "Scaffold", path: "/scaffold", icon: Wand2 },
    ],
  },
  {
    label: "Runs",
    items: [
      { label: "Dashboard", path: "/", icon: LayoutDashboard },
    ],
  },
  {
    label: "Analyze",
    items: [
      { label: "Compare", path: "/diff", icon: GitCompare },
      { label: "Bisect", path: "/bisect", icon: GitBranch },
    ],
  },
  {
    label: "System",
    items: [
      { label: "Gateway", path: "/system/gateway", icon: Radio },
      { label: "Plugins", path: "/system/plugins", icon: Puzzle },
      { label: "Doctor", path: "/system/doctor", icon: HeartPulse },
    ],
  },
];

function NavGroupSection({
  group,
  collapsed,
}: {
  group: NavGroup;
  collapsed: boolean;
}) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="mb-2">
      {!collapsed && (
        <button
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
          aria-controls={`nav-group-${group.label.replace(/\s+/g, '-').toLowerCase()}`}
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
        <ul
          id={`nav-group-${group.label.replace(/\s+/g, '-').toLowerCase()}`}
          className="space-y-0.5"
        >
          {group.items.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                end={item.path === "/"}
                title={collapsed ? item.label : undefined}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-2.5 text-sm transition-all duration-150 mx-2 rounded-md ${
                    collapsed ? "justify-center px-0 mx-0" : ""
                  } ${
                    isActive
                      ? "bg-slate-800/80 text-slate-100"
                      : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
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
          <span className="text-base font-bold text-slate-200">Binex</span>
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
          />
        ))}
      </nav>
    </aside>
  );
}
