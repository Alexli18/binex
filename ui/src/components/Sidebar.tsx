import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  Workflow,
  Wand2,
  BookOpen,
  LayoutDashboard,
  HeartPulse,
  Puzzle,
  Radio,
  Clock,
  DollarSign,
  GitCompare,
  GitBranch,
  PanelLeftClose,
  PanelLeftOpen,
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
      { label: "Editor",   path: "/editor",   icon: Workflow },
      { label: "Scaffold", path: "/scaffold",  icon: Wand2 },
      { label: "Prompts",  path: "/prompts",   icon: BookOpen },
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
      { label: "Compare", path: "/diff",    icon: GitCompare },
      { label: "Costs",   path: "/costs",   icon: DollarSign },
      { label: "Bisect",  path: "/bisect",  icon: GitBranch },
    ],
  },
  {
    label: "System",
    items: [
      { label: "Scheduler", path: "/scheduler",      icon: Clock },
      { label: "Gateway",   path: "/system/gateway", icon: Radio },
      { label: "Plugins",   path: "/system/plugins", icon: Puzzle },
      { label: "Doctor",    path: "/system/doctor",  icon: HeartPulse },
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
  return (
    <div className="mb-1">
      {!collapsed && (
        <div className="px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-slate-600 select-none">
          {group.label}
        </div>
      )}
      <ul className="space-y-px">
        {group.items.map((item) => (
          <li key={item.path}>
            <NavLink
              to={item.path}
              end={item.path === "/"}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                `relative flex items-center gap-3 text-sm transition-colors duration-100 mx-2 rounded-md ${
                  collapsed ? "justify-center px-2 py-2.5" : "px-3 py-2"
                } ${
                  isActive
                    ? "text-slate-100 bg-slate-800"
                    : "text-slate-500 hover:text-slate-300 hover:bg-slate-800/50"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && !collapsed && (
                    <span
                      className="absolute left-0 inset-y-1.5 w-0.5 rounded-full bg-emerald-500"
                      aria-hidden="true"
                    />
                  )}
                  <item.icon
                    size={15}
                    className={`shrink-0 ${isActive ? "text-emerald-400" : ""}`}
                  />
                  {!collapsed && (
                    <span className="leading-none">{item.label}</span>
                  )}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`flex h-screen flex-col border-r border-slate-800/80 bg-slate-950 transition-[width] duration-200 ease-out ${
        collapsed ? "w-[52px]" : "w-[220px]"
      }`}
    >
      {/* Brand */}
      <div
        className={`flex items-center border-b border-slate-800/80 ${
          collapsed ? "justify-center px-3 py-3.5" : "justify-between px-4 py-3.5"
        }`}
      >
        {!collapsed && (
          <div className="flex items-center gap-2 select-none">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M6 4 C12 4, 18 4, 18 8 C18 12, 12 12, 6 12 C12 12, 18 12, 18 16 C18 20, 12 20, 6 20"
                stroke="#10b981"
                strokeWidth="2"
                strokeLinecap="round"
                fill="none"
              />
              <circle cx="6"  cy="4"  r="1.5" fill="#10b981" />
              <circle cx="18" cy="8"  r="1.5" fill="#10b981" />
              <circle cx="6"  cy="12" r="1.5" fill="#10b981" />
              <circle cx="18" cy="16" r="1.5" fill="#10b981" />
              <circle cx="6"  cy="20" r="1.5" fill="#10b981" />
            </svg>
            <span className="text-sm font-semibold text-slate-200 tracking-tight">Binex</span>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="rounded-md p-1 text-slate-600 hover:text-slate-400 hover:bg-slate-800/60 transition-colors"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed
            ? <PanelLeftOpen size={15} />
            : <PanelLeftClose size={15} />
          }
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 scrollbar-none">
        {NAV_GROUPS.map((group) => (
          <NavGroupSection
            key={group.label}
            group={group}
            collapsed={collapsed}
          />
        ))}
      </nav>

      {/* Version badge */}
      {!collapsed && (
        <div className="px-4 py-3 border-t border-slate-800/80">
          <span className="text-[10px] font-mono text-slate-600">v0.7.0</span>
        </div>
      )}
    </aside>
  );
}
