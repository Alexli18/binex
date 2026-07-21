import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CallReplayModal } from './CallReplayModal';
import * as apiModule from '../lib/api';

// ModelSelect fetches providers; stub it to a plain input to keep this unit-focused.
vi.mock('./editor/ModelSelect', () => ({
  ModelSelect: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <input aria-label="model" value={value} onChange={(e) => onChange(e.target.value)} />
  ),
}));

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof apiModule>('../lib/api');
  return { ...actual, replayCall: vi.fn() };
});

const replayCall = vi.mocked(apiModule.replayCall);

function result(overrides: Partial<apiModule.ReplayCallResult> = {}): apiModule.ReplayCallResult {
  return {
    run_id: 'obs_1',
    call_id: 'call_000',
    original_model: 'gpt-4o',
    replay_model: 'gpt-4o',
    original_response: 'original text',
    replay_response: 'replay text',
    changed: true,
    cost: 0.0003,
    tool_requests: [],
    ...overrides,
  };
}

describe('CallReplayModal', () => {
  beforeEach(() => replayCall.mockReset());

  it('replays and shows the original-vs-replay comparison', async () => {
    replayCall.mockResolvedValue(result());
    render(
      <CallReplayModal runId="obs_1" callId="call_000" originalModel="gpt-4o" onClose={vi.fn()} />,
    );
    fireEvent.click(screen.getByText('Replay'));
    await waitFor(() => expect(screen.getByText('replay text')).toBeInTheDocument());
    expect(screen.getByText('original text')).toBeInTheDocument();
    expect(screen.getByText('CHANGED')).toBeInTheDocument();
  });

  it('passes a model swap to replayCall', async () => {
    replayCall.mockResolvedValue(result({ replay_model: 'gpt-4o-mini' }));
    render(
      <CallReplayModal runId="obs_1" callId="call_000" originalModel="gpt-4o" onClose={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText('model'), { target: { value: 'gpt-4o-mini' } });
    fireEvent.click(screen.getByText('Replay'));
    await waitFor(() => expect(replayCall).toHaveBeenCalled());
    expect(replayCall).toHaveBeenCalledWith('obs_1', 'call_000', {
      model: 'gpt-4o-mini',
      prompt: undefined,
    });
  });

  it('surfaces requested-but-not-executed tool calls', async () => {
    replayCall.mockResolvedValue(
      result({ tool_requests: [{ name: 'search', arguments: '{"q":"x"}' }] }),
    );
    render(
      <CallReplayModal runId="obs_1" callId="call_000" originalModel="gpt-4o" onClose={vi.fn()} />,
    );
    fireEvent.click(screen.getByText('Replay'));
    await waitFor(() => expect(screen.getByText(/not executed/)).toBeInTheDocument());
    expect(screen.getByText(/search\(/)).toBeInTheDocument();
  });

  it('shows an error when replay fails', async () => {
    replayCall.mockRejectedValueOnce(new Error('boom'));
    render(
      <CallReplayModal runId="obs_1" callId="call_000" originalModel="gpt-4o" onClose={vi.fn()} />,
    );
    fireEvent.click(screen.getByText('Replay'));
    expect(await screen.findByText('boom')).toBeInTheDocument();
  });
});
