const API_BASE_URL = 'http://localhost:8000';

type AuthHeadersProvider = () => Promise<Record<string, string>>;

let authHeadersProvider: AuthHeadersProvider = async () => ({});

export function setAuthHeadersProvider(provider: AuthHeadersProvider): void {
  authHeadersProvider = provider;
}

export type Session = {
  id: string;
  title: string;
  repo_path: string | null;
  harness: 'test' | 'codex' | 'pi';
  prompt: string | null;
  model: string | null;
  status: 'created' | 'running' | 'stopped' | 'completed' | 'errored';
  branch_name: string | null;
  log_path: string | null;
  output_tail: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type SessionCreate = {
  title: string;
  repo_path?: string;
  harness: 'test' | 'codex' | 'pi';
  prompt?: string;
  model?: string;
};

export type DocumentMetadata = {
  id: string;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  intent: string;
  temporary_storage_path: string;
  retention_expires_at: string;
  deletion_status: 'retained' | 'deleted';
  uploaded_at: string;
  uploader: string;
  is_permanent_archive: boolean;
};

export type WorkflowRun = {
  id: string;
  document_id: string;
  intent: string;
  status: 'created' | 'running' | 'completed' | 'errored';
  extraction_status: 'created' | 'running' | 'completed' | 'errored' | null;
  extraction_error: string | null;
  suggested_classification: string | null;
  extracted_fields: Record<string, unknown> | null;
  review_status: 'pending' | 'approved';
  last_reviewed_by: string | null;
  last_reviewed_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  destination_record_id: string | null;
  audit_summary: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type ReviewQueueItem = WorkflowRun & {
  document: DocumentMetadata;
};

export type ReviewRunDetail = ReviewQueueItem & {
  source_preview: {
    available: boolean;
    content: string | null;
    reason: string | null;
  };
};

export type DocumentUploadResult = {
  document: DocumentMetadata;
  workflow_run: WorkflowRun;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const authHeaders = await authHeadersProvider();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...authHeaders, ...options?.headers },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function listSessions(): Promise<Session[]> {
  return request<Session[]>('/sessions');
}

export function getSession(id: string): Promise<Session> {
  return request<Session>(`/sessions/${id}`);
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

export function resumeSession(id: string): Promise<Session> {
  return request<Session>(`/sessions/${id}/resume`, { method: 'POST' });
}

export function restartSession(id: string): Promise<Session> {
  return request<Session>(`/sessions/${id}/restart`, { method: 'POST' });
}

export async function getSessionLogs(id: string): Promise<string> {
  const result = await request<{ session_id: string; logs: string }>(`/sessions/${id}/logs`);
  return result.logs;
}

export async function uploadDocument(formData: FormData): Promise<DocumentUploadResult> {
  const authHeaders = await authHeadersProvider();
  const response = await fetch(`${API_BASE_URL}/documents/upload`, {
    method: 'POST',
    headers: authHeaders,
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<DocumentUploadResult>;
}

export async function extractWorkflowRun(id: string): Promise<WorkflowRun> {
  return request<WorkflowRun>(`/workflow-runs/${id}/extract`, { method: 'POST' });
}

export async function deleteWorkflowRun(id: string): Promise<void> {
  const authHeaders = await authHeadersProvider();
  const response = await fetch(`${API_BASE_URL}/workflow-runs/${id}`, { method: 'DELETE', headers: authHeaders });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
}

export function listReviewQueue(): Promise<ReviewQueueItem[]> {
  return request<ReviewQueueItem[]>('/workflow-runs/review-queue');
}

export function getReviewRun(id: string): Promise<ReviewRunDetail> {
  return request<ReviewRunDetail>(`/workflow-runs/${id}/review`);
}

export function updateReviewFields(id: string, reviewer: string, extractedFields: Record<string, unknown>): Promise<WorkflowRun> {
  return request<WorkflowRun>(`/workflow-runs/${id}/review/fields`, {
    method: 'PATCH',
    body: JSON.stringify({ reviewer, extracted_fields: extractedFields }),
  });
}

export function approveReviewRun(id: string, reviewer: string): Promise<WorkflowRun> {
  return request<WorkflowRun>(`/workflow-runs/${id}/review/approve`, {
    method: 'POST',
    body: JSON.stringify({ reviewer, fields_reviewed: true }),
  });
}
