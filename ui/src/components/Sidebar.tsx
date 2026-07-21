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

// Anchors the first-run guided tour (issue #32) targets, keyed by nav path.
const TOUR_ANCHORS: Record<string, string | undefined> = {
  "/editor": "nav-editor",
  "/scaffold": "nav-scaffold",
};

const AMBER = "#e8a020";
const BG = "#131315";
const BORDER = "#252528";
const MUTED = "#80808a";
const TEXT = "#f0f0f0";
const S2 = "#1a1a1d";

function NavGroupSection({ group, collapsed }: { group: NavGroup; collapsed: boolean }) {
  return (
    <div style={{ marginBottom: 4 }}>
      {!collapsed && (
        <div style={{
          padding: "6px 14px 3px",
          fontSize: 9,
          color: "#4a4a52",
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          userSelect: "none",
        }}>
          {group.label}
        </div>
      )}
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {group.items.map((item) => (
          <li key={item.path}>
            <NavLink
              to={item.path}
              end={item.path === "/"}
              data-tour={TOUR_ANCHORS[item.path]}
              title={collapsed ? item.label : undefined}
              style={({ isActive }) => ({
                display: "flex",
                alignItems: "center",
                justifyContent: collapsed ? "center" : "flex-start",
                gap: collapsed ? 0 : 8,
                padding: collapsed ? "8px 0" : "7px 14px",
                fontSize: 11,
                cursor: "pointer",
                color: isActive ? AMBER : MUTED,
                background: isActive ? "rgba(232,160,32,0.07)" : "transparent",
                borderLeft: isActive ? `2px solid ${AMBER}` : "2px solid transparent",
                transition: "all 0.1s",
                textDecoration: "none",
              })}
              onMouseEnter={(e) => {
                const el = e.currentTarget as HTMLElement;
                if (!el.getAttribute("aria-current")) {
                  el.style.color = TEXT;
                  el.style.background = S2;
                }
              }}
              onMouseLeave={(e) => {
                const el = e.currentTarget as HTMLElement;
                if (!el.getAttribute("aria-current")) {
                  el.style.color = MUTED;
                  el.style.background = "transparent";
                }
              }}
            >
              {({ isActive }) => (
                <>
                  <item.icon
                    size={13}
                    style={{ color: isActive ? AMBER : MUTED, flexShrink: 0 }}
                  />
                  {!collapsed && (
                    <span style={{ lineHeight: 1 }}>{item.label}</span>
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
  const w = collapsed ? 40 : 200;

  return (
    <aside data-tour="sidebar" style={{
      width: w,
      minWidth: w,
      height: "100vh",
      display: "flex",
      flexDirection: "column",
      background: BG,
      borderRight: `1px solid ${BORDER}`,
      transition: "width 0.15s",
      overflow: "hidden",
      flexShrink: 0,
    }}>
      {/* Brand */}
      <div style={{
        padding: collapsed ? "12px 0" : "12px 14px",
        borderBottom: `1px solid ${BORDER}`,
        display: "flex",
        alignItems: "center",
        justifyContent: collapsed ? "center" : "space-between",
        minHeight: 44,
      }}>
        {!collapsed && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, userSelect: "none" }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <defs>
                <linearGradient id="bxg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={AMBER} />
                  <stop offset="100%" stopColor="#22d3ee" />
                </linearGradient>
              </defs>
              <path
                d="M6 4 C12 4,18 4,18 8 C18 12,12 12,6 12 C12 12,18 12,18 16 C18 20,12 20,6 20"
                stroke="url(#bxg)" strokeWidth="2" strokeLinecap="round" fill="none"
              />
              <circle cx="6"  cy="4"  r="1.8" fill="url(#bxg)" />
              <circle cx="18" cy="8"  r="1.8" fill="url(#bxg)" />
              <circle cx="6"  cy="12" r="1.8" fill="url(#bxg)" />
              <circle cx="18" cy="16" r="1.8" fill="url(#bxg)" />
              <circle cx="6"  cy="20" r="1.8" fill="url(#bxg)" />
            </svg>
            <span style={{ fontSize: 13, fontWeight: 700, color: TEXT, letterSpacing: "0.04em" }}>
              binex
            </span>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: MUTED,
            padding: "2px 4px",
            fontSize: 14,
            lineHeight: 1,
            fontFamily: "inherit",
          }}
          onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = TEXT)}
          onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = MUTED)}
        >
          {collapsed ? "⊞" : "⊟"}
        </button>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, overflowY: "auto", padding: "8px 0" }}>
        {NAV_GROUPS.map((group) => (
          <NavGroupSection key={group.label} group={group} collapsed={collapsed} />
        ))}
      </nav>

      {/* Version */}
      {!collapsed && (
        <div style={{
          padding: "8px 14px",
          borderTop: `1px solid ${BORDER}`,
          fontSize: 9,
          color: "#4a4a52",
        }}>
          v0.7.1 · MIT
        </div>
      )}
    </aside>
  );
}
