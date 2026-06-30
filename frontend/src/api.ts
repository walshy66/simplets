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
  drive_file_id: string | null;
  drive_web_url: string | null;
  filename_hash: string | null;
  filename_redacted: string | null;
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
  review_status: 'pending' | 'reviewed' | 'approved';
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

export type DestinationPush = {
  id: string;
  workflow_run_id: string;
  workspace_id: string;
  provider: string;
  status: 'pending' | 'succeeded' | 'failed';
  destination_record_id: string | null;
  error_message: string | null;
  attempted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ApprovalResult = {
  workflow_run: WorkflowRun;
  destination_pushes: DestinationPush[];
  all_succeeded: boolean;
};

export type ExtractionPreview = {
  fields: Record<string, unknown>;
  suggested_classification: string | null;
};

export type ReviewRunDetail = ReviewQueueItem & {
  source_preview: {
    available: boolean;
    content: string | null;
    reason: string | null;
  };
  destination_pushes: DestinationPush[];
  improve_extraction_gate?: {
    feature_enabled: boolean;
    subscription_enabled: boolean;
    permission_allowed: boolean;
    action_enabled: boolean;
    unavailable_reason?: string | null;
  } | null;
};

export type DocumentUploadResult = {
  document: DocumentMetadata;
  workflow_run: WorkflowRun;
};

export type CurrentStateLane = {
  id: string;
  title: string;
  lane_type?: 'role-team' | 'system-application' | 'external-client' | 'other';
};

export type CurrentStatePhase = {
  id: string;
  title: string;
};

export type CurrentStatePosition = {
  x: number;
  y: number;
};

export type CurrentStateNode = {
  id: string;
  lane_id?: string | null;
  phase_id?: string | null;
  title: string;
  node_type: string;
  position?: CurrentStatePosition | null;
};

export type CurrentStateConnector = {
  id: string;
  source_node_id: string;
  target_node_id: string;
  label?: string;
};

export type CurrentStateComment = {
  id: string;
  body: string;
  node_id: string | null;
  version_ref: string | null;
  author: string | null;
  created_at: string | null;
  resolved: boolean;
};

export type CurrentStateCommentCreate = {
  body: string;
  node_id?: string | null;
  version_ref?: string | null;
  resolved?: boolean;
};

export type CurrentStateMap = {
  id: string;
  workspace_id: string;
  title: string;
  version_ref: string | null;
  status: 'draft' | 'approved' | 'archived';
  source_version_id: string | null;
  lanes: CurrentStateLane[];
  phases: CurrentStatePhase[];
  nodes: CurrentStateNode[];
  connectors: CurrentStateConnector[];
  comments: CurrentStateComment[];
  created_at: string;
  updated_at: string;
};

export type CurrentStateMapCreate = {
  title: string;
  version_ref?: string | null;
  status?: 'draft' | 'approved' | 'archived';
  source_version_id?: string | null;
  lanes?: CurrentStateLane[];
  phases?: CurrentStatePhase[];
  nodes?: CurrentStateNode[];
  connectors?: CurrentStateConnector[];
  comments?: CurrentStateComment[];
};

export type CurrentStateMapUpdate = Required<CurrentStateMapCreate>;

export type CurrentStateImportJob = {
  id: string;
  workspace_id: string;
  filename_hash: string;
  filename_redacted: string;
  filename_display: string | null;
  dismissed_at: string | null;
  file_type: string;
  uploader: string;
  status: 'pending' | 'succeeded' | 'failed';
  error_message: string | null;
  result_map_id: string | null;
  created_at: string;
  updated_at: string;
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

export function getWorkflowCanvas(): Promise<{ embed_url: string }> {
  return request<{ embed_url: string }>('/workspaces/current/canvas');
}

export type Workspace = {
  id: string;
  name: string;
  subdomain: string | null;
  branding_logo_url: string | null;
  branding_primary_color: string | null;
  activepieces_project_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ClientContext = {
  workspace: Workspace;
  drive_datastore: {
    provider: 'google_drive';
    drive_root_id: string;
    invoice_folder_id: string;
    folder_path: string | null;
  } | null;
  invoice_upload: {
    available: boolean;
    reason: string | null;
  };
};

export function getCurrentWorkspace(): Promise<Workspace> {
  return request<Workspace>('/workspaces/current');
}

export function getClientContext(): Promise<ClientContext> {
  return request<ClientContext>('/workspaces/current/client-context');
}

export function updateWorkspaceBranding(payload: {
  logo_url: string | null;
  primary_color: string | null;
}): Promise<Workspace> {
  return request<Workspace>('/workspaces/current/branding', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function uploadWorkspaceLogo(file: File): Promise<Workspace> {
  const authHeaders = await authHeadersProvider();
  const form = new FormData();
  form.append('file', file);
  const response = await fetch(`${API_BASE_URL}/workspaces/current/branding/logo`, {
    method: 'POST',
    headers: authHeaders,
    body: form,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<Workspace>;
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

export function markReviewRunReviewed(id: string, reviewer: string): Promise<WorkflowRun> {
  return request<WorkflowRun>(`/workflow-runs/${id}/review/mark-reviewed`, {
    method: 'POST',
    body: JSON.stringify({ reviewer, fields_reviewed: true }),
  });
}

export function approveReviewRun(id: string, reviewer: string): Promise<ApprovalResult> {
  return request<ApprovalResult>(`/workflow-runs/${id}/review/approve`, {
    method: 'POST',
    body: JSON.stringify({ reviewer, fields_reviewed: true }),
  });
}

export function purgeWorkflowRun(id: string): Promise<void> {
  return request<void>(`/workflow-runs/${id}`, { method: 'DELETE' });
}

export function retryDestinationPush(id: string, reviewer: string): Promise<ApprovalResult> {
  return request<ApprovalResult>(`/workflow-runs/${id}/review/retry-push`, {
    method: 'POST',
    body: JSON.stringify({ reviewer, fields_reviewed: true }),
  });
}

export function listCurrentStateMaps(): Promise<CurrentStateMap[]> {
  return request<CurrentStateMap[]>('/current-state-maps');
}

export function getCurrentStateMap(id: string): Promise<CurrentStateMap> {
  return request<CurrentStateMap>(`/current-state-maps/${id}`);
}

export function createCurrentStateMap(payload: CurrentStateMapCreate): Promise<CurrentStateMap> {
  return request<CurrentStateMap>('/current-state-maps', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateCurrentStateMap(id: string, payload: CurrentStateMapUpdate): Promise<CurrentStateMap> {
  return request<CurrentStateMap>(`/current-state-maps/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function listCurrentStateMapVersions(id: string): Promise<CurrentStateMap[]> {
  return request<CurrentStateMap[]>(`/current-state-maps/${id}/versions`);
}

export function duplicateCurrentStateMap(id: string): Promise<CurrentStateMap> {
  return request<CurrentStateMap>(`/current-state-maps/${id}/duplicate`, { method: 'POST' });
}

export function addCurrentStateMapComment(id: string, payload: CurrentStateCommentCreate): Promise<CurrentStateMap> {
  return request<CurrentStateMap>(`/current-state-maps/${id}/comments`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function acceptCurrentStateMap(id: string): Promise<CurrentStateMap> {
  return request<CurrentStateMap>(`/current-state-maps/${id}/accept`, { method: 'POST' });
}

export function listCurrentStateImports(): Promise<CurrentStateImportJob[]> {
  return request<CurrentStateImportJob[]>('/current-state-imports');
}

export async function uploadCurrentStateImport(file: File): Promise<CurrentStateImportJob> {
  const authHeaders = await authHeadersProvider();
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${API_BASE_URL}/current-state-imports`, {
    method: 'POST',
    headers: authHeaders,
    body: formData,
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<CurrentStateImportJob>;
}

export function retryCurrentStateImport(id: string): Promise<CurrentStateImportJob> {
  return request<CurrentStateImportJob>(`/current-state-imports/${id}/retry`, { method: 'POST' });
}

export function dismissCurrentStateImport(id: string): Promise<CurrentStateImportJob> {
  return request<CurrentStateImportJob>(`/current-state-imports/${id}/dismiss`, { method: 'POST' });
}

export async function submitIntakeForm(formData: FormData): Promise<DocumentUploadResult> {
  const authHeaders = await authHeadersProvider();
  const response = await fetch(`${API_BASE_URL}/submissions`, {
    method: 'POST',
    headers: authHeaders,
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<DocumentUploadResult>;
}

export async function extractPreview(formData: FormData): Promise<ExtractionPreview> {
  const authHeaders = await authHeadersProvider();
  const response = await fetch(`${API_BASE_URL}/submissions/extract-preview`, {
    method: 'POST',
    headers: authHeaders,
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<ExtractionPreview>;
}
