import { describe, it, expect } from 'vitest';
import { shouldAutoSelectFirstWorkflow } from './editor-autoselect';

/**
 * The editor opens the first workflow on disk as a convenience when it has
 * nothing to show. It used to decide that on `!selectedPath` alone — but after
 * "Open in Editor" from Scaffold the editor holds unsaved generated content and
 * *also* has no path, so the arriving workflow list hijacked it: the generated
 * workflow was replaced by an unrelated file and Save went grey ("no changes"),
 * silently discarding the user's work.
 *
 * Whether that happened depended on which won — the list request or the user's
 * click — which is what made the e2e test flaky.
 */
describe('shouldAutoSelectFirstWorkflow', () => {
  const base = {
    fileParam: null as string | null,
    selectedPath: null as string | null,
    content: '',
    workflows: ['examples/a.yaml', 'examples/b.yaml'],
  };

  it('opens the first workflow in an empty editor', () => {
    expect(shouldAutoSelectFirstWorkflow(base)).toBe(true);
  });

  it('never overwrites content the editor is already holding', () => {
    expect(
      shouldAutoSelectFirstWorkflow({ ...base, content: 'name: scaffold\n' })
    ).toBe(false);
  });

  it('treats whitespace-only content as empty', () => {
    expect(shouldAutoSelectFirstWorkflow({ ...base, content: '   \n' })).toBe(true);
  });

  it('does nothing when a file is already selected', () => {
    expect(
      shouldAutoSelectFirstWorkflow({ ...base, selectedPath: 'examples/a.yaml' })
    ).toBe(false);
  });

  it('does nothing when the URL names a file', () => {
    expect(
      shouldAutoSelectFirstWorkflow({ ...base, fileParam: 'examples/b.yaml' })
    ).toBe(false);
  });

  it('does nothing before the list has arrived', () => {
    expect(shouldAutoSelectFirstWorkflow({ ...base, workflows: undefined })).toBe(
      false
    );
  });

  it('does nothing when there are no workflows on disk', () => {
    expect(shouldAutoSelectFirstWorkflow({ ...base, workflows: [] })).toBe(false);
  });

  it('the scaffold hand-off case: content but no path — the regression', () => {
    expect(
      shouldAutoSelectFirstWorkflow({
        fileParam: null,
        selectedPath: null,
        content: 'name: scaffold\nnodes:\n  A: {}\n',
        workflows: ['examples/a2a-multi-agent.yaml'],
      })
    ).toBe(false);
  });
});
