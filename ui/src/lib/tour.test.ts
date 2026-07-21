import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Capture the config driver.js is built with so we can drive its lifecycle.
const driveMock = vi.fn();
let lastConfig: Record<string, unknown> | null = null;
vi.mock('driver.js', () => ({
  driver: vi.fn((config: Record<string, unknown>) => {
    lastConfig = config;
    return { drive: driveMock, destroy: vi.fn() };
  }),
}));
vi.mock('driver.js/dist/driver.css', () => ({}));

import {
  TOUR_STEPS,
  TOUR_STORAGE_KEY,
  createTour,
  startTour,
  hasSeenTour,
} from './tour';

describe('tour steps', () => {
  it('has five steps ending in a centered (element-less) summary', () => {
    expect(TOUR_STEPS).toHaveLength(5);
    // Every step carries a titled popover.
    for (const step of TOUR_STEPS) {
      expect(step.popover.title).toBeTruthy();
      expect(step.popover.description).toBeTruthy();
    }
    // The last step has no element → driver.js renders it centered.
    expect('element' in TOUR_STEPS[TOUR_STEPS.length - 1]).toBe(false);
  });

  it('anchors the middle steps to real data-tour targets', () => {
    const anchored = TOUR_STEPS.filter(
      (s): s is typeof s & { element: string } => 'element' in s,
    ).map((s) => s.element);
    expect(anchored).toContain('[data-tour="sidebar"]');
    expect(anchored).toContain('[data-tour="nav-editor"]');
    expect(anchored).toContain('[data-tour="nav-scaffold"]');
    expect(anchored).toContain('[data-tour="new-run"]');
  });
});

describe('tour storage', () => {
  beforeEach(() => {
    localStorage.clear();
    driveMock.mockClear();
    lastConfig = null;
  });
  afterEach(() => localStorage.clear());

  it('hasSeenTour reflects the stored flag', () => {
    expect(hasSeenTour()).toBe(false);
    localStorage.setItem(TOUR_STORAGE_KEY, '1');
    expect(hasSeenTour()).toBe(true);
  });

  it('startTour drives the tour and marks it seen on any exit', () => {
    startTour();
    expect(driveMock).toHaveBeenCalledOnce();
    expect(hasSeenTour()).toBe(false); // not seen until it ends

    // Simulate driver.js finishing/skipping — onDestroyed persists the flag.
    (lastConfig?.onDestroyed as () => void)();
    expect(hasSeenTour()).toBe(true);
  });

  it('createTour does not persist until onFinish is invoked', () => {
    const onFinish = vi.fn();
    createTour(onFinish);
    expect(onFinish).not.toHaveBeenCalled();
    (lastConfig?.onDestroyed as () => void)();
    expect(onFinish).toHaveBeenCalledOnce();
  });
});
