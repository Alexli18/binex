# Binex UI/UX Improvement Log

## Iteration 1 — 2026-03-20
**Change:** Added colored accent strip, icon badge with tinted background, and type subtitle to collapsed nodes for visual hierarchy
**File:** ui/src/components/editor/EditableNode.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — nodes now have clear type identity at a glance
**Decision:** kept
**Reason:** Previously all collapsed nodes were flat boxes with only a thin border color difference. Now each node has: (1) a 3px colored accent bar at the top for instant type recognition, (2) an icon in a tinted rounded badge instead of bare icon, (3) a two-line layout with node name (prominent) and type label (secondary) creating clear visual hierarchy. No new dependencies, single file change.

## Iteration 2 — 2026-03-20
**Change:** Unified expanded node header with collapsed node style — accent strip, icon badge, type subtitle
**File:** ui/src/components/editor/EditableNode.tsx
**Eval:** tsc: pass | vite build: pass | visual: better — expanded and collapsed views now feel like the same component
**Decision:** kept
**Reason:** Expanded header previously had a bare icon and thick colored border, inconsistent with the new collapsed style. Now uses the same accent strip + icon badge + type label pattern. Also removed heavy border-2 in favor of subtle border with tinted background for a more refined look.
