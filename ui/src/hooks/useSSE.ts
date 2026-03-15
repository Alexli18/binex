import { useEffect, useRef, useState, useCallback } from 'react';
import type { RunEvent, HumanPromptEvent } from '../lib/types';

export interface HumanOutputEvent {
  type: 'human:output';
  node_id: string;
  label: string;
  artifacts: Array<{ id: string; type: string; content: string; produced_by: string | null }>;
}

export type SSEConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

export interface SSEError {
  message: string;
  timestamp: string;
}

const MAX_RECONNECT_DELAY = 30_000;
const BASE_RECONNECT_DELAY = 1_000;

export function useSSE(runId: string | undefined) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [connectionState, setConnectionState] = useState<SSEConnectionState>('disconnected');
  const [lastError, setLastError] = useState<SSEError | null>(null);
  const [pendingPrompt, setPendingPrompt] = useState<HumanPromptEvent | null>(null);
  const [outputResult, setOutputResult] = useState<HumanOutputEvent | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seenEventIdsRef = useRef(new Set<string>());
  const isTerminalRef = useRef(false);

  const clearPrompt = useCallback(() => setPendingPrompt(null), []);
  const clearOutput = useCallback(() => setOutputResult(null), []);

  const addEvent = useCallback((event: RunEvent, eventId?: string) => {
    if (eventId) {
      if (seenEventIdsRef.current.has(eventId)) return;
      seenEventIdsRef.current.add(eventId);
    }
    setEvents((prev) => [...prev, event]);
  }, []);

  const connect = useCallback(() => {
    if (!runId || isTerminalRef.current) return;

    // Clean up existing connection
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    const isReconnect = reconnectAttemptRef.current > 0;
    setConnectionState(isReconnect ? 'reconnecting' : 'connecting');

    const es = new EventSource(`/api/v1/runs/${runId}/events`);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
      setConnectionState('connected');
      setLastError(null);
      reconnectAttemptRef.current = 0;
    };

    es.onerror = () => {
      setConnected(false);

      // Don't reconnect for terminal states
      if (isTerminalRef.current) {
        setConnectionState('disconnected');
        return;
      }

      setLastError({
        message: 'SSE connection lost',
        timestamp: new Date().toISOString(),
      });

      es.close();
      esRef.current = null;

      // Exponential backoff reconnect
      const attempt = reconnectAttemptRef.current;
      const delay = Math.min(BASE_RECONNECT_DELAY * Math.pow(2, attempt), MAX_RECONNECT_DELAY);
      reconnectAttemptRef.current = attempt + 1;

      setConnectionState('reconnecting');
      reconnectTimerRef.current = setTimeout(() => {
        connect();
      }, delay);
    };

    const eventTypes = [
      'node:started',
      'node:completed',
      'node:failed',
      'run:completed',
      'run:cancelled',
    ];
    for (const type of eventTypes) {
      es.addEventListener(type, (e: MessageEvent) => {
        const event = JSON.parse(e.data) as RunEvent;
        addEvent(event, (e as MessageEvent & { lastEventId?: string }).lastEventId || undefined);

        // Terminal events — stop reconnecting
        if (type === 'run:completed' || type === 'run:cancelled') {
          isTerminalRef.current = true;
          es.close();
          esRef.current = null;
          setConnectionState('disconnected');
        }
      });
    }

    // Human-in-the-loop prompt events
    es.addEventListener('human:prompt_needed', (e: MessageEvent) => {
      const prompt = JSON.parse(e.data) as HumanPromptEvent;
      setPendingPrompt(prompt);
      addEvent(
        { ...prompt, timestamp: new Date().toISOString() },
        (e as MessageEvent & { lastEventId?: string }).lastEventId || undefined,
      );
    });

    // Human output events
    es.addEventListener('human:output', (e: MessageEvent) => {
      const output = JSON.parse(e.data) as HumanOutputEvent;
      setOutputResult(output);
      addEvent(
        { type: 'node:completed', node_id: output.node_id, timestamp: new Date().toISOString() },
        (e as MessageEvent & { lastEventId?: string }).lastEventId || undefined,
      );
    });
  }, [runId, addEvent]);

  useEffect(() => {
    if (!runId) return;

    // Reset state for new runId
    isTerminalRef.current = false;
    reconnectAttemptRef.current = 0;
    seenEventIdsRef.current = new Set();
    setEvents([]);
    setConnectionState('disconnected');
    setLastError(null);

    connect();

    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      setConnected(false);
      setConnectionState('disconnected');
    };
  }, [runId, connect]);

  return {
    events,
    connected,
    connectionState,
    lastError,
    pendingPrompt,
    clearPrompt,
    outputResult,
    clearOutput,
  };
}
