import { ChangeEvent, useMemo, useState } from 'react';
import {
  ApprovalResult,
  approveReviewRun,
  deleteWorkflowRun,
  extractWorkflowRun,
  updateReviewFields,
  uploadDocument,
  WorkflowRun,
} from '../api';
import {
  buildInvoiceImportFormData,
  canImportInvoice,
  DEMO_INVOICE_CLIENTS,
  ImportClient,
  searchInvoiceClients,
} from '../clientInvoiceImportModel';
import { formatApprovalOutcome, invoiceFieldRows } from '../reviewQueueModel';

const CURRENT_REVIEWER = 'local-reviewer';

type ModalStep = 'select' | 'importing' | 'review' | 'approving' | 'success' | 'error';

export default function ClientsPage() {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <div className="clients-page">
      <section className="panel clients-hero" aria-labelledby="clients-title">
        <div>
          <p className="eyebrow">Client operations</p>
          <h2 id="clients-title">Clients</h2>
          <p>Quickly ingest supplier invoices for a client, review extracted data, then approve distribution to connected apps.</p>
        </div>
        <button type="button" className="primary-action" onClick={() => setIsOpen(true)}>
          Upload invoice
        </button>
      </section>
      <section className="panel">
        <h3>Active clients</h3>
        <div className="client-list">
          {DEMO_INVOICE_CLIENTS.map((client) => (
            <div key={client.id} className="client-card">
              <strong>{client.name}</strong>
              <span>{client.email}</span>
            </div>
          ))}
        </div>
      </section>
      {isOpen ? <InvoiceImportModal onClose={() => setIsOpen(false)} /> : null}
    </div>
  );
}

function InvoiceImportModal({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState<ModalStep>('select');
  const [query, setQuery] = useState('');
  const [selectedClient, setSelectedClient] = useState<ImportClient | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [workflowRun, setWorkflowRun] = useState<WorkflowRun | null>(null);
  const [fieldsDraft, setFieldsDraft] = useState('{}');
  const [approval, setApproval] = useState<ApprovalResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const matches = useMemo(() => searchInvoiceClients(query), [query]);
  const draft = { client: selectedClient, file };

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
  }

  async function importInvoice() {
    if (!canImportInvoice(draft)) return;
    setStep('importing');
    setError(null);
    try {
      const upload = await uploadDocument(buildInvoiceImportFormData(draft));
      const extracted = await extractWorkflowRun(upload.workflow_run.id);
      setWorkflowRun(extracted);
      setFieldsDraft(JSON.stringify(extracted.extracted_fields ?? {}, null, 2));
      setStep('review');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invoice import failed');
      setStep('error');
    }
  }

  async function approveInvoice() {
    if (!workflowRun) return;
    setStep('approving');
    setError(null);
    try {
      const parsedFields = JSON.parse(fieldsDraft) as Record<string, unknown>;
      await updateReviewFields(workflowRun.id, CURRENT_REVIEWER, parsedFields);
      const result = await approveReviewRun(workflowRun.id, CURRENT_REVIEWER);
      setApproval(result);
      setStep(result.all_succeeded ? 'success' : 'review');
      if (!result.all_succeeded) setError('One or more destination pushes failed. Fix the connector issue, then retry approval.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approval failed');
      setStep('review');
    }
  }

  async function cancelImport() {
    if (workflowRun) {
      try {
        await deleteWorkflowRun(workflowRun.id);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Cancel failed; imported data was not deleted.');
        return;
      }
    }
    onClose();
  }

  function resetForRetry() {
    setStep('select');
    setWorkflowRun(null);
    setFieldsDraft('{}');
    setApproval(null);
    setError(null);
  }

  const fieldsAreValid = (() => {
    try {
      JSON.parse(fieldsDraft);
      return true;
    } catch {
      return false;
    }
  })();

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="invoice-modal" role="dialog" aria-modal="true" aria-labelledby="invoice-modal-title">
        <header className="invoice-modal-header">
          <div>
            <p className="eyebrow">Invoice ingestion</p>
            <h2 id="invoice-modal-title">Import invoice</h2>
          </div>
          <button type="button" className="icon-button" aria-label="Close import modal" onClick={cancelImport}>×</button>
        </header>

        {error ? <p className="session-error">{error}</p> : null}

        {step === 'select' || step === 'importing' || step === 'error' ? (
          <div className="invoice-modal-body">
            <label>
              Assign to client *
              <input className="form-control" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search client name or email" />
            </label>
            <div className="client-search-results" aria-label="Client search results">
              {matches.map((client) => (
                <button
                  key={client.id}
                  type="button"
                  className={selectedClient?.id === client.id ? 'client-result selected' : 'client-result'}
                  onClick={() => {
                    setSelectedClient(client);
                    setQuery(client.name);
                  }}
                >
                  <strong>{client.name}</strong>
                  <span>{client.email}</span>
                </button>
              ))}
            </div>
            <label>
              Invoice file *
              <input className="form-control" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.txt" onChange={onFileChange} />
            </label>
            {file ? <p className="session-status">Ready to import {file.name} for {selectedClient?.name ?? 'selected client'}.</p> : null}
          </div>
        ) : null}

        {step === 'review' || step === 'approving' ? (
          <div className="invoice-modal-body">
            <p className="session-status">Review extracted invoice data for {selectedClient?.name}. Edit any incorrect fields before approval.</p>
            {workflowRun?.extracted_fields ? (
              <div className="invoice-field-list" aria-label="Extracted invoice fields">
                {invoiceFieldRows(workflowRun.extracted_fields).map((field) => (
                  <div key={field.key} className={field.isMissingOrUncertain ? 'invoice-field-row invoice-field-attention' : 'invoice-field-row'}>
                    <strong>{field.label}</strong>
                    <span>{field.displayValue}</span>
                    <em>{field.provenanceLabel}</em>
                  </div>
                ))}
              </div>
            ) : null}
            <label>
              Editable field payload
              <textarea className="form-control" rows={10} value={fieldsDraft} onChange={(event) => setFieldsDraft(event.target.value)} />
            </label>
            {!fieldsAreValid ? <p className="session-error">Field payload must be valid JSON before approval.</p> : null}
          </div>
        ) : null}

        {step === 'success' ? (
          <div className="invoice-modal-body">
            <p className="session-status">{approval ? formatApprovalOutcome(approval) : 'Approved and distributed.'}</p>
          </div>
        ) : null}

        <footer className="invoice-modal-actions">
          {step === 'select' || step === 'error' ? (
            <button type="button" onClick={importInvoice} disabled={!canImportInvoice(draft)}>
              Import and extract
            </button>
          ) : null}
          {step === 'importing' ? <button type="button" disabled>Importing…</button> : null}
          {step === 'review' ? (
            <>
              <button type="button" onClick={approveInvoice} disabled={!fieldsAreValid}>Approve and send</button>
              <button type="button" onClick={resetForRetry}>Replace file / retry extraction</button>
            </>
          ) : null}
          {step === 'approving' ? <button type="button" disabled>Approving…</button> : null}
          {step === 'success' ? <button type="button" onClick={onClose}>Done</button> : null}
          {step !== 'success' ? <button type="button" className="secondary-action" onClick={cancelImport}>Cancel import</button> : null}
        </footer>
      </section>
    </div>
  );
}
