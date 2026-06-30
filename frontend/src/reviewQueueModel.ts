export type SourcePreview = {
  available: boolean;
  content: string | null;
  reason: string | null;
};

export type ReviewApprovalState = {
  hasOpenedExtractedDataScreen: boolean;
  fieldsAreValid: boolean;
};

export type PushOutcome = {
  provider: string;
  status: 'pending' | 'succeeded' | 'failed';
  destination_record_id: string | null;
  error_message: string | null;
};

export type ApprovalOutcome = {
  all_succeeded: boolean;
  destination_pushes: PushOutcome[];
};

export type InvoiceReviewStatusInput = {
  review_status: 'pending' | 'reviewed' | 'approved';
  document: { deletion_status: 'retained' | 'deleted' };
};

export type InvoiceFieldRow = {
  key: string;
  label: string;
  displayValue: string;
  provenanceLabel: string;
  isMissingOrUncertain: boolean;
  flagReason: string | null;
};

export type ImproveExtractionGate = {
  feature_enabled: boolean;
  subscription_enabled: boolean;
  permission_allowed: boolean;
  action_enabled: boolean;
  unavailable_reason?: string | null;
};

export type ImproveExtractionControl = {
  visible: boolean;
  enabled: boolean;
  label: string;
  message: string;
};

const MVP_INVOICE_FIELDS: { key: string; label: string }[] = [
  { key: 'invoice_number', label: 'Invoice number' },
  { key: 'vendor_name', label: 'Vendor' },
  { key: 'invoice_date', label: 'Invoice date' },
  { key: 'due_date', label: 'Due date' },
  { key: 'total_amount', label: 'Total amount' },
  { key: 'currency', label: 'Currency' },
];

export function parseEditableFields(value: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error('extracted fields must be valid JSON');
  }

  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('extracted fields must be a JSON object');
  }

  return parsed as Record<string, unknown>;
}

export function canSaveExtractedFields(value: string): boolean {
  try {
    parseEditableFields(value);
    return true;
  } catch {
    return false;
  }
}

export function canApproveReviewRun(state: ReviewApprovalState): boolean {
  return state.hasOpenedExtractedDataScreen && state.fieldsAreValid;
}

export function formatSourcePreview(sourcePreview: SourcePreview): string {
  if (sourcePreview.available) {
    return sourcePreview.content || '';
  }
  return `Source unavailable: ${sourcePreview.reason || 'not available'}`;
}

export function formatApprovalOutcome(outcome: ApprovalOutcome): string {
  if (outcome.all_succeeded) {
    const records = outcome.destination_pushes
      .filter((push) => push.destination_record_id)
      .map((push) => `${push.provider}: ${push.destination_record_id}`);
    const suffix = records.length > 0 ? ` (${records.join(', ')})` : '';
    return `Approved. Data pushed to all destinations and purged from SimpleTS${suffix}.`;
  }
  const failed = outcome.destination_pushes.filter((push) => push.status === 'failed');
  const failures = failed.map((push) => `${push.provider}: ${push.error_message ?? 'push failed'}`).join('; ');
  return `Some destinations failed — data is retained until resolved. ${failures}`;
}

/** Names of fields the extraction flagged for reviewer attention. */
export function flaggedFieldNames(extractedFields: Record<string, unknown> | null): string[] {
  if (!extractedFields) {
    return [];
  }
  const meta = extractedFields['_extraction'] as { flagged_fields?: unknown } | undefined;
  if (!meta || !Array.isArray(meta.flagged_fields)) {
    return [];
  }
  return meta.flagged_fields.filter((name): name is string => typeof name === 'string');
}

export function flagReason(extractedFields: Record<string, unknown> | null, fieldName: string): string | null {
  if (!extractedFields) {
    return null;
  }
  const meta = extractedFields['_extraction'] as
    | { field_details?: Record<string, { flag_reason?: string | null }> }
    | undefined;
  return meta?.field_details?.[fieldName]?.flag_reason ?? null;
}

export function hasFailedPushes(pushes: PushOutcome[]): boolean {
  return pushes.some((push) => push.status === 'failed');
}

export function invoiceReviewStatus(item: InvoiceReviewStatusInput): 'Needs review' | 'Reviewed' | 'Purged' {
  if (item.document.deletion_status === 'deleted') {
    return 'Purged';
  }
  return item.review_status === 'reviewed' || item.review_status === 'approved' ? 'Reviewed' : 'Needs review';
}

function formatInvoiceValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return 'Missing';
  }
  if (typeof value === 'number') {
    return String(value);
  }
  if (typeof value === 'string') {
    return value;
  }
  return JSON.stringify(value);
}

function extractionFieldDetails(extractedFields: Record<string, unknown> | null, fieldName: string) {
  const meta = extractedFields?.['_extraction'] as
    | { field_details?: Record<string, { source?: string | null; confidence?: string | number | null; flag_reason?: string | null }> }
    | undefined;
  return meta?.field_details?.[fieldName] ?? null;
}

function provenanceLabel(source: unknown, confidence: unknown): string {
  const sourceLabel = typeof source === 'string' && source.trim() ? source : 'Provenance unavailable';
  const confidenceLabel =
    typeof confidence === 'string' || typeof confidence === 'number' ? `${confidence} confidence` : 'confidence unavailable';
  return `${sourceLabel} · ${confidenceLabel}`;
}

function hasWeakOrIncompleteExtraction(extractedFields: Record<string, unknown> | null): boolean {
  return invoiceFieldRows(extractedFields).some((field) => field.isMissingOrUncertain);
}

export function getImproveExtractionControl({
  extractedFields,
  gate,
}: {
  extractedFields: Record<string, unknown> | null;
  gate: ImproveExtractionGate | null | undefined;
}): ImproveExtractionControl {
  if (!hasWeakOrIncompleteExtraction(extractedFields)) {
    return { visible: false, enabled: false, label: 'Improve extraction', message: '' };
  }

  const failClosedGate = gate ?? {
    feature_enabled: false,
    subscription_enabled: false,
    permission_allowed: false,
    action_enabled: false,
    unavailable_reason: 'Enhanced extraction is not available for this workspace.',
  };
  const enabled =
    failClosedGate.feature_enabled &&
    failClosedGate.subscription_enabled &&
    failClosedGate.permission_allowed &&
    failClosedGate.action_enabled;

  if (enabled) {
    return {
      visible: true,
      enabled: true,
      label: 'Improve extraction',
      message: 'Uses workspace usage allowance/usage units. It will only run after you choose this action.',
    };
  }

  return {
    visible: true,
    enabled: false,
    label: 'Improve extraction',
    message:
      failClosedGate.unavailable_reason ??
      'Enhanced extraction is not enabled yet. No workspace usage allowance/usage units will be consumed.',
  };
}

export function invoiceFieldRows(extractedFields: Record<string, unknown> | null): InvoiceFieldRow[] {
  return MVP_INVOICE_FIELDS.map((field) => {
    const details = extractionFieldDetails(extractedFields, field.key);
    const value = extractedFields?.[field.key];
    const flagged = flaggedFieldNames(extractedFields).includes(field.key);
    const missing = value === null || value === undefined || value === '';
    const confidence = details?.confidence;
    const uncertain = typeof confidence === 'string' && ['low', 'uncertain', 'missing'].includes(confidence.toLowerCase());
    return {
      key: field.key,
      label: field.label,
      displayValue: formatInvoiceValue(value),
      provenanceLabel: provenanceLabel(details?.source, confidence),
      isMissingOrUncertain: missing || flagged || uncertain,
      flagReason: details?.flag_reason ?? null,
    };
  });
}
