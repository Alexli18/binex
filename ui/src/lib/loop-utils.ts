import type { Node } from 'reactflow';
import type { ExitCondition } from './loop-types';

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
  const resolved = resolveJsonPath(artifact, condition.jsonpath);
  const fieldName = condition.jsonpath.replace('$.', '');
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
      pass = String(resolved) === condition.value;
      break;
    case '!=':
      pass = String(resolved) !== condition.value;
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
      pass = String(resolved).includes(condition.value);
      break;
  }

  const details = pass
    ? `${resolved} ${condition.operator} ${condition.value}`
    : `${resolved} not ${condition.operator} ${condition.value}`;

  return { pass, expression, details };
}
