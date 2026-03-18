import type { Node, Edge } from 'reactflow';
import type { ExitCondition } from './loop-types';

/* ── Layout constants ── */
export const LOOP_PADDING = { top: 80, bottom: 80, left: 20, right: 20 };
export const NODE_W = 180;
export const NODE_H = 50;
export const GAP = 20;

/**
 * Find the next free grid position inside a loop container.
 * Scans row-by-row, column-by-column for an unoccupied cell.
 */
export function getNextFreePosition(
  loopNode: Node,
  existingChildren: Node[],
): { x: number; y: number } {
  const loopW = (loopNode.style?.width as number) || 450;
  const usableW = loopW - LOOP_PADDING.left - LOOP_PADDING.right;
  const cols = Math.max(1, Math.floor((usableW + GAP) / (NODE_W + GAP)));

  const occupied = new Set<string>();
  for (const child of existingChildren) {
    const col = Math.round((child.position.x - LOOP_PADDING.left) / (NODE_W + GAP));
    const row = Math.round((child.position.y - LOOP_PADDING.top) / (NODE_H + GAP));
    occupied.add(`${col},${row}`);
  }

  for (let row = 0; row < 100; row++) {
    for (let col = 0; col < cols; col++) {
      if (!occupied.has(`${col},${row}`)) {
        return {
          x: LOOP_PADDING.left + col * (NODE_W + GAP),
          y: LOOP_PADDING.top + row * (NODE_H + GAP),
        };
      }
    }
  }
  return { x: LOOP_PADDING.left, y: LOOP_PADDING.top };
}

/**
 * Calculate required loop container size to fit all children.
 */
export function calculateLoopSize(
  children: Node[],
): { width: number; height: number } {
  if (children.length === 0) return { width: 450, height: 200 };

  let maxX = 0;
  let maxY = 0;
  for (const child of children) {
    maxX = Math.max(maxX, child.position.x + NODE_W);
    maxY = Math.max(maxY, child.position.y + NODE_H);
  }

  return {
    width: Math.max(450, maxX + LOOP_PADDING.right),
    height: Math.max(200, maxY + LOOP_PADDING.bottom),
  };
}

/**
 * Find if a drop position falls inside a loop container node.
 * Returns the loop node ID or null.
 */
export function findParentLoop(
  dropPosition: { x: number; y: number },
  loopNodes: Node[],
): string | null {
  for (const loop of loopNodes) {
    const w = (loop.style?.width as number) || 450;
    const h = (loop.style?.height as number) || 250;
    if (
      dropPosition.x >= loop.position.x &&
      dropPosition.x <= loop.position.x + w &&
      dropPosition.y >= loop.position.y &&
      dropPosition.y <= loop.position.y + h
    ) {
      return loop.id;
    }
  }
  return null;
}

/**
 * Get absolute position of a node, accounting for parentNode offset.
 */
export function getAbsolutePosition(
  node: Node,
  allNodes: Node[],
): { x: number; y: number } {
  if (!node.parentNode) return node.position;
  const parent = allNodes.find((n) => n.id === node.parentNode);
  if (!parent) return node.position;
  return {
    x: parent.position.x + node.position.x,
    y: parent.position.y + node.position.y,
  };
}

export interface LoopFlowInfo {
  entryNodeIds: string[];
  exitNodeIds: string[];
  entryLabels: string[];
  exitLabels: string[];
}

/**
 * Determine entry/exit nodes of a loop container from the React Flow graph.
 * Entry = no internal incoming edges. Exit = no internal outgoing edges.
 * Supports explicit overrides via entryNode/outputNode labels.
 */
export function getLoopFlowInfo(
  loopId: string,
  nodes: Node[],
  edges: Edge[],
  overrideEntry?: string,
  overrideOutput?: string,
): LoopFlowInfo {
  const children = nodes.filter((n) => n.parentNode === loopId);
  const childIds = new Set(children.map((n) => n.id));

  if (children.length === 0) {
    return { entryNodeIds: [], exitNodeIds: [], entryLabels: [], exitLabels: [] };
  }

  const internalEdges = edges.filter(
    (e) => childIds.has(e.source) && childIds.has(e.target),
  );

  const hasInternalIncoming = new Set(internalEdges.map((e) => e.target));
  const hasInternalOutgoing = new Set(internalEdges.map((e) => e.source));

  let entryNodes = children.filter((n) => !hasInternalIncoming.has(n.id));
  let exitNodes = children.filter((n) => !hasInternalOutgoing.has(n.id));

  // Apply overrides if set
  if (overrideEntry) {
    const found = children.filter((n) => n.data?.label === overrideEntry);
    if (found.length > 0) entryNodes = found;
  }
  if (overrideOutput) {
    const found = children.filter((n) => n.data?.label === overrideOutput);
    if (found.length > 0) exitNodes = found;
  }

  // Fallback: single node is both entry and exit
  if (children.length === 1) {
    entryNodes = children;
    exitNodes = children;
  }

  return {
    entryNodeIds: entryNodes.map((n) => n.id),
    exitNodeIds: exitNodes.map((n) => n.id),
    entryLabels: entryNodes.map((n) => n.data?.label ?? n.id),
    exitLabels: exitNodes.map((n) => n.data?.label ?? n.id),
  };
}

/**
 * Simple JSONPath evaluator for $.key.subkey patterns.
 * Does NOT support full JSONPath spec — only dot-notation access.
 */
function resolveJsonPath(obj: unknown, path: string): unknown {
  if (!path.startsWith('$.')) return undefined;
  const keys = path.slice(2).split('.');
  let current: unknown = obj;
  for (const key of keys) {
    if (current == null || typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

/**
 * Evaluate an exit condition against an artifact value.
 */
export function evaluateExitCondition(
  condition: ExitCondition,
  artifact: unknown,
): { pass: boolean; expression: string; details: string } {
  const resolved = resolveJsonPath(artifact, condition.field);
  const fieldName = condition.field.replace('$.', '');
  const expression = `${fieldName}: ${JSON.stringify(resolved)} ${condition.operator} ${condition.value}`;

  if (resolved == null) {
    return { pass: false, expression, details: `${fieldName} is null/undefined` };
  }

  const numResolved = Number(resolved);
  const numTarget = Number(condition.value);
  const isNumeric = !isNaN(numResolved) && !isNaN(numTarget);

  let pass = false;
  switch (condition.operator) {
    case '==':
      pass = String(resolved) === String(condition.value);
      break;
    case '!=':
      pass = String(resolved) !== String(condition.value);
      break;
    case '>':
      pass = isNumeric && numResolved > numTarget;
      break;
    case '<':
      pass = isNumeric && numResolved < numTarget;
      break;
    case '>=':
      pass = isNumeric && numResolved >= numTarget;
      break;
    case '<=':
      pass = isNumeric && numResolved <= numTarget;
      break;
    case 'contains':
      pass = String(resolved).includes(String(condition.value));
      break;
  }

  const details = pass
    ? `${resolved} ${condition.operator} ${condition.value}`
    : `${resolved} not ${condition.operator} ${condition.value}`;

  return { pass, expression, details };
}
