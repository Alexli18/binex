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

export { ApiError };
