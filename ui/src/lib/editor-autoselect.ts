/**
 * When may the editor open the first workflow on disk by itself?
 *
 * Only when it has nothing to show. Deciding this on "no file is selected"
 * alone is not enough: after **Open in Editor** from Scaffold the editor holds
 * unsaved generated content and has no path either, so the arriving workflow
 * list replaced the generated workflow with an unrelated file and greyed out
 * Save ("no changes") — silently discarding the user's work.
 */
export interface AutoSelectState {
  /** `?file=` from the URL, if any. */
  fileParam: string | null;
  /** The file currently open, if any. */
  selectedPath: string | null;
  /** What the editor is holding right now. */
  content: string;
  /** Workflow list; undefined until it arrives. */
  workflows: string[] | undefined;
}

export function shouldAutoSelectFirstWorkflow({
  fileParam,
  selectedPath,
  content,
  workflows,
}: AutoSelectState): boolean {
  if (fileParam) return false;
  if (selectedPath) return false;
  // The guard that was missing: never clobber content already in the editor.
  if (content.trim()) return false;
  return !!workflows && workflows.length > 0;
}
