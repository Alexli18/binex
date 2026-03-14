import { useEffect, useRef, useState, useCallback } from 'react';
import type { RunEvent, HumanPromptEvent } from '../lib/types';

export interface HumanOutputEvent {
  type: 'human:output';
  node_id: string;
  label: string;
  artifacts: Array<{ id: string; type: string; content: string; produced_by: string | null }>;
}

export function useSSE(runId: string | undefined) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [pendingPrompt, setPendingPrompt] = useState<HumanPromptEvent | null>(null);
  const [outputResult, setOutputResult] = useState<HumanOutputEvent | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const clearPrompt = useCallback(() => setPendingPrompt(null), []);
  const clearOutput = useCallback(() => setOutputResult(null), []);

  useEffect(() => {
    if (!runId) return;
    const es = new EventSource(`/api/v1/runs/${runId}/events`);
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);

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
        setEvents((prev) => [...prev, event]);
      });
    }

    // Human-in-the-loop prompt events
    es.addEventListener('human:prompt_needed', (e: MessageEvent) => {
      const prompt = JSON.parse(e.data) as HumanPromptEvent;
      setPendingPrompt(prompt);
      setEvents((prev) => [...prev, { ...prompt, timestamp: new Date().toISOString() }]);
    });

    // Human output events — display results
    es.addEventListener('human:output', (e: MessageEvent) => {
      const output = JSON.parse(e.data) as HumanOutputEvent;
      setOutputResult(output);
      setEvents((prev) => [...prev, { type: 'node:completed', node_id: output.node_id, timestamp: new Date().toISOString() }]);
    });

    return () => {
      es.close();
      esRef.current = null;
      setConnected(false);
    };
  }, [runId]);

  return { events, connected, pendingPrompt, clearPrompt, outputResult, clearOutput };
}
