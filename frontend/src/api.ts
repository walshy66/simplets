const API_BASE_URL = 'http://localhost:8000';

export type Session = {
  id: string;
  title: string;
  repo_path: string | null;
  harness: 'test' | 'codex' | 'pi';
  prompt: string | null;
  status: 'created' | 'running' | 'stopped' | 'completed' | 'errored';
  branch_name: string | null;
  log_path: string | null;
  created_at: string;
  updated_at: string;
};

export type SessionCreate = {
  title: string;
  repo_path?: string;
  harness: 'test' | 'codex' | 'pi';
  prompt?: string;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function listSessions(): Promise<Session[]> {
  return request<Session[]>('/sessions');
}

export function createSession(payload: SessionCreate): Promise<Session> {
  return request<Session>('/sessions', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function startSession(id: string): Promise<Session> {
  return request<Session>(`/sessions/${id}/start`, { method: 'POST' });
}

export function stopSession(id: string): Promise<Session> {
  return request<Session>(`/sessions/${id}/stop`, { method: 'POST' });
}

export async function getSessionLogs(id: string): Promise<string> {
  const result = await request<{ session_id: string; logs: string }>(`/sessions/${id}/logs`);
  return result.logs;
}
