import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useSSE } from './useSSE';

// Mock EventSource
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {};
  readyState = 0;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (e: MessageEvent) => void) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(handler);
  }

  close() {
    this.closed = true;
    this.readyState = 2;
  }

  // Test helper: simulate an event
  _emit(type: string, data: unknown, id?: string) {
    const event = { data: JSON.stringify(data), lastEventId: id } as MessageEvent;
    for (const handler of this.listeners[type] ?? []) {
      handler(event);
    }
  }

  // Test helper: simulate open
  _open() {
    this.readyState = 1;
    this.onopen?.();
  }

  // Test helper: simulate error
  _error() {
    this.onerror?.();
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.useFakeTimers();
  (globalThis as any).EventSource = MockEventSource;
});

afterEach(() => {
  vi.useRealTimers();
  delete (globalThis as any).EventSource;
});

describe('useSSE', () => {
  it('returns disconnected state when no runId', () => {
    const { result } = renderHook(() => useSSE(undefined));
    expect(result.current.connectionState).toBe('disconnected');
    expect(result.current.events).toEqual([]);
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it('creates EventSource with correct URL', () => {
    renderHook(() => useSSE('run-123'));
    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toBe('/api/v1/runs/run-123/events');
  });

  it('sets connected state on open', () => {
    const { result } = renderHook(() => useSSE('run-1'));
    act(() => {
      MockEventSource.instances[0]._open();
    });
    expect(result.current.connected).toBe(true);
    expect(result.current.connectionState).toBe('connected');
  });

  it('processes node:started events', () => {
    const { result } = renderHook(() => useSSE('run-1'));
    const es = MockEventSource.instances[0];
    act(() => {
      es._open();
      es._emit('node:started', { type: 'node:started', node_id: 'a', timestamp: 't1' }, 'e1');
    });
    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0].node_id).toBe('a');
  });

  it('deduplicates events by eventId', () => {
    const { result } = renderHook(() => useSSE('run-1'));
    const es = MockEventSource.instances[0];
    act(() => {
      es._open();
      es._emit('node:started', { type: 'node:started', node_id: 'a', timestamp: 't1' }, 'dup-1');
      es._emit('node:started', { type: 'node:started', node_id: 'a', timestamp: 't1' }, 'dup-1');
    });
    expect(result.current.events).toHaveLength(1);
  });

  it('sets disconnected on terminal event (run:completed)', () => {
    const { result } = renderHook(() => useSSE('run-1'));
    const es = MockEventSource.instances[0];
    act(() => {
      es._open();
      es._emit('run:completed', { type: 'run:completed', timestamp: 't2' }, 'e2');
    });
    expect(result.current.connectionState).toBe('disconnected');
    expect(es.closed).toBe(true);
  });

  it('handles error and attempts reconnect', () => {
    const { result } = renderHook(() => useSSE('run-1'));
    const es = MockEventSource.instances[0];
    act(() => {
      es._open();
    });
    act(() => {
      es._error();
    });
    expect(result.current.connected).toBe(false);
    expect(result.current.lastError?.message).toBe('SSE connection lost');
    expect(result.current.connectionState).toBe('reconnecting');

    // Advance timer to trigger reconnect
    act(() => {
      vi.advanceTimersByTime(1500);
    });
    expect(MockEventSource.instances.length).toBe(2);
  });

  it('resets state when runId changes', () => {
    const { result, rerender } = renderHook(
      ({ id }: { id: string | undefined }) => useSSE(id),
      { initialProps: { id: 'run-1' } },
    );
    const es = MockEventSource.instances[0];
    act(() => {
      es._open();
      es._emit('node:started', { type: 'node:started', node_id: 'a', timestamp: 't1' }, 'e1');
    });
    expect(result.current.events).toHaveLength(1);

    rerender({ id: 'run-2' });
    expect(result.current.events).toHaveLength(0);
    expect(es.closed).toBe(true);
  });

  it('closes EventSource on unmount', () => {
    const { unmount } = renderHook(() => useSSE('run-1'));
    const es = MockEventSource.instances[0];
    unmount();
    expect(es.closed).toBe(true);
  });

  it('handles human:prompt_needed events', () => {
    const { result } = renderHook(() => useSSE('run-1'));
    const es = MockEventSource.instances[0];
    const prompt = {
      type: 'human:prompt_needed',
      prompt_id: 'p1',
      prompt_type: 'approval',
      node_id: 'n1',
      message: 'Approve?',
      artifacts: [],
    };
    act(() => {
      es._open();
      es._emit('human:prompt_needed', prompt, 'hp1');
    });
    expect(result.current.pendingPrompt).toMatchObject({ prompt_id: 'p1' });
  });

  it('clearPrompt clears pending prompt', () => {
    const { result } = renderHook(() => useSSE('run-1'));
    const es = MockEventSource.instances[0];
    act(() => {
      es._open();
      es._emit(
        'human:prompt_needed',
        { type: 'human:prompt_needed', prompt_id: 'p1', prompt_type: 'input', node_id: 'n1', message: 'hi', artifacts: [] },
        'hp1',
      );
    });
    expect(result.current.pendingPrompt).toBeTruthy();
    act(() => {
      result.current.clearPrompt();
    });
    expect(result.current.pendingPrompt).toBeNull();
  });
});
