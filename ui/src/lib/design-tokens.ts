/**
 * Binex Design Tokens — Amber Dark Theme
 *
 * Single source of truth for colors, spacing, and visual properties.
 * Palette: amber #e8a020 primary, warm dark #0b0b0c base, JetBrains Mono.
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
    bg: 'bg-amber-500/15',
    text: 'text-amber-400',
    border: 'border-amber-500/40',
    dot: 'bg-amber-400',
  },
  failed: {
    bg: 'bg-red-500/15',
    text: 'text-red-400',
    border: 'border-red-500/40',
    dot: 'bg-red-400',
  },
  cancelled: {
    bg: 'bg-zinc-500/15',
    text: 'text-zinc-400',
    border: 'border-zinc-500/40',
    dot: 'bg-zinc-400',
  },
  pending: {
    bg: 'bg-zinc-500/10',
    text: 'text-zinc-500',
    border: 'border-zinc-600/40',
    dot: 'bg-zinc-500',
  },
  skipped: {
    bg: 'bg-zinc-500/10',
    text: 'text-zinc-500',
    border: 'border-zinc-600/30',
    dot: 'bg-zinc-600',
  },
  over_budget: {
    bg: 'bg-red-500/15',
    text: 'text-red-400',
    border: 'border-red-500/40',
    dot: 'bg-red-400',
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
// Hex values match NodePalette NODE_COLOR constants.
// ---------------------------------------------------------------------------
export const nodeTypeColors = {
  llm: {
    bg: 'bg-amber-500/15',
    text: 'text-amber-400',
    border: 'border-amber-500/40',
    icon: 'text-amber-400',
    hex: '#e8a020',
  },
  local: {
    bg: 'bg-cyan-500/15',
    text: 'text-cyan-400',
    border: 'border-cyan-500/40',
    icon: 'text-cyan-400',
    hex: '#22d3ee',
  },
  a2a: {
    bg: 'bg-pink-500/15',
    text: 'text-pink-400',
    border: 'border-pink-500/40',
    icon: 'text-pink-400',
    hex: '#f472b6',
  },
  human: {
    bg: 'bg-emerald-500/15',
    text: 'text-emerald-400',
    border: 'border-emerald-500/40',
    icon: 'text-emerald-400',
    hex: '#22c55e',
  },
  cao: {
    bg: 'bg-orange-500/15',
    text: 'text-orange-400',
    border: 'border-orange-500/40',
    icon: 'text-orange-400',
    hex: '#f97316',
  },
  pattern: {
    bg: 'bg-violet-500/15',
    text: 'text-violet-400',
    border: 'border-violet-500/40',
    icon: 'text-violet-400',
    hex: '#a78bfa',
  },
} as const;

export type NodeType = keyof typeof nodeTypeColors;

// ---------------------------------------------------------------------------
// Semantic colors — generic purpose-based palette
// ---------------------------------------------------------------------------
export const colors = {
  primary: {
    DEFAULT: 'text-amber-400',
    hover: 'hover:text-amber-300',
    bg: 'bg-amber-500',
    bgSubtle: 'bg-amber-500/15',
    border: 'border-amber-500',
  },
  success: {
    DEFAULT: 'text-emerald-400',
    hover: 'hover:text-emerald-300',
    bg: 'bg-emerald-500',
    bgSubtle: 'bg-emerald-500/15',
    border: 'border-emerald-500',
  },
  danger: {
    DEFAULT: 'text-red-400',
    hover: 'hover:text-red-300',
    bg: 'bg-red-500',
    bgSubtle: 'bg-red-500/15',
    border: 'border-red-500',
  },
  warning: {
    DEFAULT: 'text-amber-400',
    hover: 'hover:text-amber-300',
    bg: 'bg-amber-500',
    bgSubtle: 'bg-amber-500/15',
    border: 'border-amber-500',
  },
  info: {
    DEFAULT: 'text-cyan-400',
    hover: 'hover:text-cyan-300',
    bg: 'bg-cyan-500',
    bgSubtle: 'bg-cyan-500/15',
    border: 'border-cyan-500',
  },
  muted: {
    DEFAULT: 'text-zinc-400',
    hover: 'hover:text-zinc-300',
    bg: 'bg-zinc-800',
    bgSubtle: 'bg-zinc-800/50',
    border: 'border-zinc-700',
  },
} as const;

// ---------------------------------------------------------------------------
// Surface / layout tokens
// ---------------------------------------------------------------------------
export const surface = {
  base: 'bg-[#0b0b0c]',
  raised: 'bg-[#131315]',
  overlay: 'bg-[#1a1a1d]',
  hover: 'hover:bg-[#1a1a1d]',
  border: 'border-[#252528]',
  divider: 'border-[#252528]',
} as const;

// ---------------------------------------------------------------------------
// Chart colors — hex values for Recharts / SVG (not Tailwind classes)
// ---------------------------------------------------------------------------
export const chartColors = {
  primary: '#e8a020',       // amber — primary accent
  primaryFill: '#e8a02040', // amber/25
  secondary: '#22d3ee',     // cyan
  tertiary: '#f472b6',      // magenta
  quaternary: '#22c55e',    // green
  quinary: '#f97316',       // orange
  grid: '#252528',
  axis: '#4a4a52',
  edge: '#333338',
  tooltipBg: '#1a1a1d',
  tooltipBorder: '#252528',
  cao: '#f97316',
} as const;

// ---------------------------------------------------------------------------
// Diff colors — for inline diffs (additions/deletions)
// ---------------------------------------------------------------------------
export const diffColors = {
  added: { bg: 'bg-emerald-900/40', text: 'text-emerald-300' },
  removed: { bg: 'bg-red-900/40', text: 'text-red-300' },
  hunk: 'text-amber-400',
} as const;

// ---------------------------------------------------------------------------
// Typography helpers
// ---------------------------------------------------------------------------
export const typography = {
  heading: 'text-[#f0f0f0] font-semibold',
  body: 'text-[#80808a]',
  muted: 'text-[#4a4a52]',
  code: 'font-mono text-sm',
} as const;

// ---------------------------------------------------------------------------
// Helper: get status token set (with fallback)
// ---------------------------------------------------------------------------
export function getStatusColors(status: string) {
  return (
    statusColors[status as Status] ?? {
      bg: 'bg-zinc-500/10',
      text: 'text-zinc-400',
      border: 'border-zinc-600/30',
      dot: 'bg-zinc-500',
    }
  );
}

// ---------------------------------------------------------------------------
// Helper: get node type token set (with fallback)
// ---------------------------------------------------------------------------
export function getNodeTypeColors(nodeType: string) {
  return (
    nodeTypeColors[nodeType as NodeType] ?? {
      bg: 'bg-zinc-500/10',
      text: 'text-zinc-400',
      border: 'border-zinc-600/30',
      icon: 'text-zinc-400',
      hex: '#4a4a52',
    }
  );
}
