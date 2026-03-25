/**
 * Binex Design Tokens
 *
 * Single source of truth for colors, spacing, and visual properties.
 * Dark theme primary (slate-900/950 base).
 *
 * All Tailwind class values here map to the custom palette defined
 * in tailwind.config.ts so they survive PurgeCSS.
 */

// ---------------------------------------------------------------------------
// Status colors — workflow node execution states
// ---------------------------------------------------------------------------
export const statusColors = {
  completed: {
    bg: 'bg-emerald-500/15',
    text: 'text-emerald-400',
    border: 'border-emerald-500/40',
    dot: 'bg-emerald-400',
  },
  running: {
    bg: 'bg-blue-500/15',
    text: 'text-blue-400',
    border: 'border-blue-500/40',
    dot: 'bg-blue-400',
  },
  failed: {
    bg: 'bg-red-500/15',
    text: 'text-red-400',
    border: 'border-red-500/40',
    dot: 'bg-red-400',
  },
  cancelled: {
    bg: 'bg-slate-500/15',
    text: 'text-slate-400',
    border: 'border-slate-500/40',
    dot: 'bg-slate-400',
  },
  pending: {
    bg: 'bg-slate-500/10',
    text: 'text-slate-500',
    border: 'border-slate-600/40',
    dot: 'bg-slate-500',
  },
  skipped: {
    bg: 'bg-slate-500/10',
    text: 'text-slate-500',
    border: 'border-slate-600/30',
    dot: 'bg-slate-600',
  },
  over_budget: {
    bg: 'bg-amber-500/15',
    text: 'text-amber-400',
    border: 'border-amber-500/40',
    dot: 'bg-amber-400',
  },
  interrupted: {
    bg: 'bg-orange-500/15',
    text: 'text-orange-400',
    border: 'border-orange-500/40',
    dot: 'bg-orange-400',
  },
} as const;

export type Status = keyof typeof statusColors;

// ---------------------------------------------------------------------------
// Node type colors — agent type prefixes (llm://, local://, a2a://, human://, cao://)
// ---------------------------------------------------------------------------
export const nodeTypeColors = {
  llm: {
    bg: 'bg-violet-500/15',
    text: 'text-violet-400',
    border: 'border-violet-500/40',
    icon: 'text-violet-400',
  },
  local: {
    bg: 'bg-cyan-500/15',
    text: 'text-cyan-400',
    border: 'border-cyan-500/40',
    icon: 'text-cyan-400',
  },
  a2a: {
    bg: 'bg-indigo-500/15',
    text: 'text-indigo-400',
    border: 'border-indigo-500/40',
    icon: 'text-indigo-400',
  },
  human: {
    bg: 'bg-amber-500/15',
    text: 'text-amber-400',
    border: 'border-amber-500/40',
    icon: 'text-amber-400',
  },
  cao: {
    bg: 'bg-purple-500/15',
    text: 'text-purple-400',
    border: 'border-purple-500/40',
    icon: 'text-purple-400',
  },
  pattern: {
    bg: 'bg-pink-500/15',
    text: 'text-pink-400',
    border: 'border-pink-500/40',
    icon: 'text-pink-400',
  },
} as const;

export type NodeType = keyof typeof nodeTypeColors;

// ---------------------------------------------------------------------------
// Semantic colors — generic purpose-based palette
// ---------------------------------------------------------------------------
export const colors = {
  primary: {
    DEFAULT: 'text-blue-500',
    hover: 'hover:text-blue-400',
    bg: 'bg-blue-500',
    bgSubtle: 'bg-blue-500/15',
    border: 'border-blue-500',
  },
  success: {
    DEFAULT: 'text-emerald-500',
    hover: 'hover:text-emerald-400',
    bg: 'bg-emerald-500',
    bgSubtle: 'bg-emerald-500/15',
    border: 'border-emerald-500',
  },
  danger: {
    DEFAULT: 'text-red-500',
    hover: 'hover:text-red-400',
    bg: 'bg-red-500',
    bgSubtle: 'bg-red-500/15',
    border: 'border-red-500',
  },
  warning: {
    DEFAULT: 'text-amber-500',
    hover: 'hover:text-amber-400',
    bg: 'bg-amber-500',
    bgSubtle: 'bg-amber-500/15',
    border: 'border-amber-500',
  },
  info: {
    DEFAULT: 'text-cyan-500',
    hover: 'hover:text-cyan-400',
    bg: 'bg-cyan-500',
    bgSubtle: 'bg-cyan-500/15',
    border: 'border-cyan-500',
  },
  muted: {
    DEFAULT: 'text-slate-400',
    hover: 'hover:text-slate-300',
    bg: 'bg-slate-800',
    bgSubtle: 'bg-slate-800/50',
    border: 'border-slate-700',
  },
} as const;

// ---------------------------------------------------------------------------
// Surface / layout tokens
// ---------------------------------------------------------------------------
export const surface = {
  /** Main page background */
  base: 'bg-slate-950',
  /** Slightly raised surface (cards, panels) */
  raised: 'bg-slate-900',
  /** Overlay / modal background */
  overlay: 'bg-slate-800/50',
  /** Interactive hover for rows/items */
  hover: 'hover:bg-slate-800/60',
  /** Default border for cards/panels */
  border: 'border-slate-700/60',
  /** Subtle divider */
  divider: 'border-slate-800',
} as const;

// ---------------------------------------------------------------------------
// Chart colors — hex values for Recharts / SVG (not Tailwind classes)
// ---------------------------------------------------------------------------
export const chartColors = {
  primary: '#3b82f6',       // blue-500
  primaryFill: '#3b82f680', // blue-500/50
  secondary: '#8b5cf6',     // violet-500
  grid: '#334155',          // slate-700
  axis: '#94a3b8',          // slate-400
  edge: '#64748b',          // slate-500
  tooltipBg: '#1e293b',     // slate-800
  tooltipBorder: '#475569', // slate-600
  cao: '#a855f7',           // purple-500
} as const;

// ---------------------------------------------------------------------------
// Diff colors — for inline diffs (additions/deletions)
// ---------------------------------------------------------------------------
export const diffColors = {
  added: { bg: 'bg-green-900/40', text: 'text-green-300' },
  removed: { bg: 'bg-red-900/40', text: 'text-red-300' },
  hunk: 'text-blue-400',
} as const;

// ---------------------------------------------------------------------------
// Typography helpers
// ---------------------------------------------------------------------------
export const typography = {
  heading: 'text-slate-100 font-semibold',
  body: 'text-slate-300',
  muted: 'text-slate-500',
  code: 'font-mono text-sm',
} as const;

// ---------------------------------------------------------------------------
// Helper: get status token set (with fallback)
// ---------------------------------------------------------------------------
export function getStatusColors(status: string) {
  return (
    statusColors[status as Status] ?? {
      bg: 'bg-slate-500/10',
      text: 'text-slate-400',
      border: 'border-slate-600/30',
      dot: 'bg-slate-500',
    }
  );
}

// ---------------------------------------------------------------------------
// Helper: get node type token set (with fallback)
// ---------------------------------------------------------------------------
export function getNodeTypeColors(nodeType: string) {
  return (
    nodeTypeColors[nodeType as NodeType] ?? {
      bg: 'bg-slate-500/10',
      text: 'text-slate-400',
      border: 'border-slate-600/30',
      icon: 'text-slate-400',
    }
  );
}
