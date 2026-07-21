import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import type { ReactNode } from 'react';

const startTourMock = vi.fn();
const hasSeenTourMock = vi.fn();
vi.mock('../lib/tour', () => ({
  startTour: () => startTourMock(),
  hasSeenTour: () => hasSeenTourMock(),
}));

const useRunsMock = vi.fn();
vi.mock('./useRuns', () => ({
  useRuns: () => useRunsMock(),
}));

import { useFirstRunTour } from './useFirstRunTour';

function wrapperAt(path: string) {
  return ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
  );
}

function runsResult(runs: unknown[] | undefined, isSuccess = true) {
  return { data: runs, isSuccess };
}

describe('useFirstRunTour', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    startTourMock.mockClear();
    hasSeenTourMock.mockReturnValue(false);
    useRunsMock.mockReturnValue(runsResult([]));
  });
  afterEach(() => vi.useRealTimers());

  it('auto-starts on an empty Dashboard for a first-time user', () => {
    renderHook(() => useFirstRunTour(), { wrapper: wrapperAt('/') });
    vi.advanceTimersByTime(500);
    expect(startTourMock).toHaveBeenCalledOnce();
  });

  it('does not start when there are existing runs', () => {
    useRunsMock.mockReturnValue(runsResult([{ id: 'r1' }]));
    renderHook(() => useFirstRunTour(), { wrapper: wrapperAt('/') });
    vi.advanceTimersByTime(500);
    expect(startTourMock).not.toHaveBeenCalled();
  });

  it('does not start when the tour was already seen', () => {
    hasSeenTourMock.mockReturnValue(true);
    renderHook(() => useFirstRunTour(), { wrapper: wrapperAt('/') });
    vi.advanceTimersByTime(500);
    expect(startTourMock).not.toHaveBeenCalled();
  });

  it('does not start off the Dashboard route', () => {
    renderHook(() => useFirstRunTour(), { wrapper: wrapperAt('/editor') });
    vi.advanceTimersByTime(500);
    expect(startTourMock).not.toHaveBeenCalled();
  });

  it('waits for the runs query before deciding', () => {
    useRunsMock.mockReturnValue(runsResult(undefined, false));
    renderHook(() => useFirstRunTour(), { wrapper: wrapperAt('/') });
    vi.advanceTimersByTime(500);
    expect(startTourMock).not.toHaveBeenCalled();
  });

  it('does not start under browser automation (navigator.webdriver)', () => {
    Object.defineProperty(navigator, 'webdriver', {
      value: true,
      configurable: true,
    });
    try {
      renderHook(() => useFirstRunTour(), { wrapper: wrapperAt('/') });
      vi.advanceTimersByTime(500);
      expect(startTourMock).not.toHaveBeenCalled();
    } finally {
      Reflect.deleteProperty(navigator, 'webdriver');
    }
  });

  it('starts at most once per mount', () => {
    const { rerender } = renderHook(() => useFirstRunTour(), {
      wrapper: wrapperAt('/'),
    });
    vi.advanceTimersByTime(500);
    rerender();
    vi.advanceTimersByTime(500);
    expect(startTourMock).toHaveBeenCalledOnce();
  });
});
