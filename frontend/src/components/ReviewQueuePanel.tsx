import { useEffect, useState } from 'react';
import {
  ApprovalResult,
  approveReviewRun,
  getReviewRun,
  listReviewQueue,
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
  hasFailedPushes,
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
  const showRetry = lastApproval !== null && !lastApproval.all_succeeded;

  return (
    <section className="panel review-queue-panel" aria-labelledby="review-queue-title">
      <h2 id="review-queue-title">Shared review queue</h2>
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
          <h3>Pending workflow runs</h3>
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
          <h3>Source preview and extracted data</h3>
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
              <label>
                Editable extracted fields
                <textarea
                  className="form-control"
                  value={fieldsDraft}
                  rows={8}
                  onChange={(event) => setFieldsDraft(event.target.value)}
                />
              </label>
              {!fieldsAreValid ? <p className="session-error">Extracted fields must be a JSON object.</p> : null}
              <div className="review-actions">
                <button type="button" onClick={saveFields} disabled={!fieldsAreValid || isSaving}>
                  {isSaving ? 'Saving…' : 'Save extracted fields'}
                </button>
                <button
                  type="button"
                  onClick={approveSelected}
                  disabled={!canApproveReviewRun({ hasOpenedExtractedDataScreen, fieldsAreValid }) || isSaving}
                >
                  Approve reviewed run
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
