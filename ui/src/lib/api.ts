const API_BASE = '/api/v1';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new ApiError(resp.status, body.error || resp.statusText);
  }
  return resp.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) =>
    request<T>(path, { method: 'DELETE' }),
};

// CAO adapter helpers
export interface CaoSession {
  terminal_id: string;
  run_id: string;
  node_name: string;
  started_at: string;
  status: string;
}

export interface CaoHealthStatus {
  status: 'online' | 'degraded' | 'offline';
  server_url: string;
}

export function getCaoHealth(): Promise<CaoHealthStatus> {
  return api.get('/cao/health');
}

export function startCaoServer(): Promise<{ status: string; pid?: number; error?: string }> {
  return api.post('/cao/server/start');
}

export function stopCaoServer(): Promise<{ status: string }> {
  return api.post('/cao/server/stop');
}

export function getCaoProfiles(): Promise<{ profiles: string[] }> {
  return api.get('/cao/profiles');
}

export function getCaoSessions(): Promise<{ sessions: CaoSession[] }> {
  return api.get('/cao/sessions');
}

export function deleteCaoSession(terminalId: string): Promise<{ ok: boolean }> {
  return api.delete(`/cao/sessions/${encodeURIComponent(terminalId)}`);
}

export function sendCaoTerminalInput(terminalId: string, message: string): Promise<{ ok: boolean }> {
  return api.post(`/cao/terminals/${encodeURIComponent(terminalId)}/input`, { message });
}

// Stateless single-call replay of an observed run (#74)
export interface ReplayCallResult {
  run_id: string;
  call_id: string;
  original_model: string;
  replay_model: string;
  original_response: string;
  replay_response: string;
  changed: boolean;
  cost: number | null;
  tool_requests: { name: string; arguments: string }[];
}

export function replayCall(
  runId: string,
  callId: string,
  opts?: { model?: string; prompt?: string; mock_response?: string },
): Promise<ReplayCallResult> {
  return api.post<ReplayCallResult>(
    `/runs/${encodeURIComponent(runId)}/calls/${encodeURIComponent(callId)}/replay`,
    opts ?? {},
  );
}

export { ApiError };
