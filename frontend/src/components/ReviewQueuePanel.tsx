import { useEffect, useState } from 'react';
import {
  ApprovalResult,
  approveReviewRun,
  getReviewRun,
  listReviewQueue,
  markReviewRunReviewed,
  purgeWorkflowRun,
  retryDestinationPush,
  ReviewQueueItem,
  ReviewRunDetail,
  updateReviewFields,
} from '../api';
import ReviewQueueRow from './ReviewQueueRow';
import {
  canApproveReviewRun,
  canSaveExtractedFields,
  flagReason,
  flaggedFieldNames,
  formatApprovalOutcome,
  formatSourcePreview,
  getImproveExtractionControl,
  hasFailedPushes,
  invoiceFieldRows,
  parseEditableFields,
} from '../reviewQueueModel';

const CURRENT_REVIEWER = 'local-reviewer';

export default function ReviewQueuePanel() {
  const [queue, setQueue] = useState<ReviewQueueItem[]>([]);
  const [selected, setSelected] = useState<ReviewRunDetail | null>(null);
  const [fieldsDraft, setFieldsDraft] = useState('{}');
  const [hasOpenedExtractedDataScreen, setHasOpenedExtractedDataScreen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [approvalCompletion, setApprovalCompletion] = useState<string | null>(null);
  const [lastApproval, setLastApproval] = useState<ApprovalResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refreshQueue() {
    setError(null);
    try {
      setQueue(await listReviewQueue());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Review queue failed to load');
    }
  }

  useEffect(() => {
    refreshQueue();
  }, []);

  async function openRun(workflowRunId: string) {
    setIsLoading(true);
    setError(null);
    try {
      const detail = await getReviewRun(workflowRunId);
      setApprovalCompletion(null);
      setSelected(detail);
      setFieldsDraft(JSON.stringify(detail.extracted_fields ?? {}, null, 2));
      setHasOpenedExtractedDataScreen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Workflow run failed to open');
    } finally {
      setIsLoading(false);
    }
  }

  async function saveFields() {
    if (!selected || !canSaveExtractedFields(fieldsDraft)) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const workflowRun = await updateReviewFields(selected.id, CURRENT_REVIEWER, parseEditableFields(fieldsDraft));
      setSelected({ ...selected, ...workflowRun });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Extracted fields failed to save');
    } finally {
      setIsSaving(false);
    }
  }

  function handleApprovalResult(result: ApprovalResult) {
    setLastApproval(result);
    setApprovalCompletion(formatApprovalOutcome(result));
    if (result.all_succeeded) {
      setSelected(null);
    }
  }

  async function markReviewed() {
    if (!selected || !canApproveReviewRun({ hasOpenedExtractedDataScreen, fieldsAreValid: canSaveExtractedFields(fieldsDraft) })) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const workflowRun = await markReviewRunReviewed(selected.id, CURRENT_REVIEWER);
      setSelected({ ...selected, ...workflowRun });
      await refreshQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Workflow run failed to mark reviewed');
    } finally {
      setIsSaving(false);
    }
  }

  async function approveSelected() {
    if (!selected || !canApproveReviewRun({ hasOpenedExtractedDataScreen, fieldsAreValid: canSaveExtractedFields(fieldsDraft) })) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      handleApprovalResult(await approveReviewRun(selected.id, CURRENT_REVIEWER));
      await refreshQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Workflow run failed to approve');
    } finally {
      setIsSaving(false);
    }
  }

  async function purgeSelected() {
    if (!selected) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      await purgeWorkflowRun(selected.id);
      setSelected(null);
      setApprovalCompletion('Retained draft data was purged from SimpleTS.');
      await refreshQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Workflow run failed to purge');
    } finally {
      setIsSaving(false);
    }
  }

  async function retryFailedPushes() {
    const runId = lastApproval?.workflow_run.id ?? selected?.id;
    if (!runId) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      handleApprovalResult(await retryDestinationPush(runId, CURRENT_REVIEWER));
      await refreshQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Retry failed');
    } finally {
      setIsSaving(false);
    }
  }

  const fieldsAreValid = canSaveExtractedFields(fieldsDraft);
  const currentFlagged = selected ? flaggedFieldNames(selected.extracted_fields) : [];
  const improveExtractionControl = selected
    ? getImproveExtractionControl({ extractedFields: selected.extracted_fields, gate: selected.improve_extraction_gate })
    : null;
  const showRetry = lastApproval !== null && !lastApproval.all_succeeded;

  return (
    <section className="panel review-queue-panel" aria-labelledby="review-queue-title">
      <h2 id="review-queue-title">Standard document processing review queue</h2>
      <button type="button" onClick={refreshQueue} disabled={isLoading || isSaving}>
        Refresh queue
      </button>
      {error ? <p className="session-error">{error}</p> : null}
      {approvalCompletion ? (
        <p className={showRetry ? 'session-error' : 'session-status'}>{approvalCompletion}</p>
      ) : null}
      {showRetry ? (
        <button type="button" onClick={retryFailedPushes} disabled={isSaving}>
          Retry failed destinations
        </button>
      ) : null}
      <div className="review-queue-layout">
        <div>
          <h3>Invoice reviews</h3>
          {queue.length === 0 ? (
            <p>No pending workflow runs.</p>
          ) : (
            <div className="dash-qlist">
              {queue.map((item) => (
                <ReviewQueueRow
                  key={item.id}
                  item={item}
                  onReview={openRun}
                  selected={selected?.id === item.id}
                />
              ))}
            </div>
          )}
        </div>
        <div className="review-detail">
          <h3>Invoice review detail</h3>
          {selected ? (
            <>
              <p>
                Reviewing {selected.document.filename} as {CURRENT_REVIEWER}. Retention expires{' '}
                {new Date(selected.document.retention_expires_at).toLocaleString()}.
              </p>
              <pre className="source-preview">{formatSourcePreview(selected.source_preview)}</pre>
              {currentFlagged.length > 0 ? (
                <div className="flagged-fields" role="alert">
                  <strong>Fields needing attention:</strong>
                  <ul>
                    {currentFlagged.map((name) => (
                      <li key={name}>
                        {name} — {flagReason(selected.extracted_fields, name) ?? 'flagged by extraction'}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {hasFailedPushes(selected.destination_pushes ?? []) ? (
                <div className="flagged-fields" role="alert">
                  <strong>Previous destination failures:</strong>
                  <ul>
                    {selected.destination_pushes
                      .filter((push) => push.status === 'failed')
                      .map((push) => (
                        <li key={push.id}>
                          {push.provider}: {push.error_message ?? 'push failed'}
                        </li>
                      ))}
                  </ul>
                </div>
              ) : null}
              <div className="invoice-field-list" aria-label="MVP invoice fields">
                {invoiceFieldRows(selected.extracted_fields).map((field) => (
                  <div
                    className={field.isMissingOrUncertain ? 'invoice-field-row invoice-field-attention' : 'invoice-field-row'}
                    key={field.key}
                  >
                    <div>
                      <strong>{field.label}</strong>
                      <span>{field.provenanceLabel}</span>
                    </div>
                    <div>
                      <span>{field.displayValue}</span>
                      {field.isMissingOrUncertain ? (
                        <em>{field.flagReason ?? 'Missing or uncertain — please confirm before approval.'}</em>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
              {improveExtractionControl?.visible ? (
                <div className="improve-extraction-card">
                  <button type="button" disabled={!improveExtractionControl.enabled || isSaving} onClick={() => setError('Enhanced extraction is not enabled yet. No workspace usage allowance/usage units will be consumed.')}>
                    {improveExtractionControl.label}
                  </button>
                  <p>{improveExtractionControl.message}</p>
                </div>
              ) : null}
              <details className="invoice-field-editor">
                <summary>Edit extracted field JSON</summary>
                <p className="session-status">Notes and comments are durable: do not include sensitive client data, raw extracted values, document contents, or secrets.</p>
                <label>
                  Editable extracted fields
                  <textarea
                    className="form-control"
                    value={fieldsDraft}
                    rows={8}
                    onChange={(event) => setFieldsDraft(event.target.value)}
                  />
                </label>
              </details>
              {!fieldsAreValid ? <p className="session-error">Extracted fields must be a JSON object.</p> : null}
              <div className="review-actions">
                <button type="button" onClick={saveFields} disabled={!fieldsAreValid || isSaving}>
                  {isSaving ? 'Saving…' : 'Save extracted fields'}
                </button>
                <button
                  type="button"
                  onClick={markReviewed}
                  disabled={!canApproveReviewRun({ hasOpenedExtractedDataScreen, fieldsAreValid }) || isSaving}
                >
                  Mark reviewed
                </button>
                <button
                  type="button"
                  onClick={approveSelected}
                  disabled={!canApproveReviewRun({ hasOpenedExtractedDataScreen, fieldsAreValid }) || isSaving}
                >
                  Approve reviewed run
                </button>
                <button type="button" onClick={purgeSelected} disabled={isSaving}>
                  Delete/Purge draft data
                </button>
              </div>
            </>
          ) : (
            <p>Open a pending run to review the source document and extracted fields before approval.</p>
          )}
        </div>
      </div>
    </section>
  );
}
