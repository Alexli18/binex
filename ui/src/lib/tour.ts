import { driver, type Driver, type DriveStep } from 'driver.js';
import 'driver.js/dist/driver.css';

/**
 * First-run guided tour (issue #32).
 *
 * A lightweight 5-step walkthrough pointing new users at the key areas of the
 * Web UI. Built on driver.js (spotlight overlay, keyboard nav, resize-aware
 * positioning) so we don't reimplement any of that ourselves.
 *
 * Steps anchor to `data-tour="..."` attributes in the layout. The last step has
 * no element, so driver.js renders it as a centered popover.
 */

export const TOUR_STORAGE_KEY = 'binex.tour.v1.done';

/** Steps are exported so the test suite can assert their shape without a DOM. */
export const TOUR_STEPS = [
  {
    element: '[data-tour="sidebar"]',
    popover: {
      title: 'Welcome to Binex',
      description:
        'This sidebar navigates between building workflows, running them, and analyzing the results. Take a 30-second tour — or skip it with the × (you won’t be asked again).',
    },
  },
  {
    element: '[data-tour="nav-editor"]',
    popover: {
      title: 'Editor',
      description:
        'Design a workflow on a visual drag-and-drop canvas or in YAML — the two stay in sync.',
    },
  },
  {
    element: '[data-tour="nav-scaffold"]',
    popover: {
      title: 'Scaffold',
      description:
        'No workflow yet? Generate a starter one from a plain-English prompt, then refine it in the Editor.',
    },
  },
  {
    element: '[data-tour="new-run"]',
    popover: {
      title: 'Run a workflow',
      description:
        'Launch a workflow here. Pick one, optionally set variables, and it runs — appearing in the list below.',
    },
  },
  {
    popover: {
      title: 'Inspect the results',
      description:
        'Once a run finishes, open it to Debug, Trace, and Lineage. Press ⌘K anytime for the command palette. You’re all set!',
    },
  },
] as const;

/**
 * Build (but do not start) the tour. `onFinish` fires whenever the tour ends —
 * completed, skipped, or dismissed — so the caller can persist the "seen" flag
 * exactly once for all exit paths ("don't show again").
 */
export function createTour(onFinish?: () => void): Driver {
  const d = driver({
    showProgress: true,
    allowClose: true,
    overlayColor: 'rgba(0,0,0,0.72)',
    stagePadding: 6,
    stageRadius: 6,
    progressText: 'Step {{current}} of {{total}}',
    nextBtnText: 'Next',
    prevBtnText: 'Back',
    doneBtnText: 'Done',
    steps: TOUR_STEPS as unknown as DriveStep[],
    onDestroyed: () => {
      onFinish?.();
    },
  });
  return d;
}

/** Convenience: build the tour, mark it seen on exit, and start it. */
export function startTour(): Driver {
  const d = createTour(() => {
    try {
      localStorage.setItem(TOUR_STORAGE_KEY, '1');
    } catch {
      /* localStorage may be unavailable (private mode) — non-fatal */
    }
  });
  d.drive();
  return d;
}

export function hasSeenTour(): boolean {
  try {
    return localStorage.getItem(TOUR_STORAGE_KEY) === '1';
  } catch {
    return true; // if storage is unreadable, don't nag
  }
}
