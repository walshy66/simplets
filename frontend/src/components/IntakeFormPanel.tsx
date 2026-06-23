import { FormEvent, useEffect, useRef, useState } from 'react';
import { ClientContext, extractPreview, getClientContext, submitIntakeForm } from '../api';
import {
  INTAKE_DRAFT_STORAGE_KEY,
  INTAKE_FIELDS,
  INTAKE_INTENT,
  IntakeFormValues,
  applyExtractedFields,
  buildSubmissionFields,
  draftHasContent,
  emptyIntakeForm,
  intakeSections,
  missingRequiredFields,
  parseDraft,
  serializeDraft,
} from '../intakeFormModel';

export default function IntakeFormPanel() {
  const [values, setValues] = useState<IntakeFormValues>(() => emptyIntakeForm());
  const [submitter, setSubmitter] = useState('');
  const [draftNotice, setDraftNotice] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [extractionNotice, setExtractionNotice] = useState<string | null>(null);
  const [flaggedFields, setFlaggedFields] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submittedRunId, setSubmittedRunId] = useState<string | null>(null);
  const [clientContext, setClientContext] = useState<ClientContext | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const restoredRef = useRef(false);

  useEffect(() => {
    getClientContext()
      .then(setClientContext)
      .catch(() => setError('We could not confirm upload setup for this client page.'));
  }, []);

  useEffect(() => {
    const draft = parseDraft(window.localStorage.getItem(INTAKE_DRAFT_STORAGE_KEY));
    if (draft && draftHasContent(draft.values, draft.submitter)) {
      setValues(draft.values);
      setSubmitter(draft.submitter);
      setDraftNotice(
        draft.savedAt
          ? `Draft restored from ${new Date(draft.savedAt).toLocaleString()}.`
          : 'Draft restored from this browser.',
      );
    }
    restoredRef.current = true;
  }, []);

  useEffect(() => {
    if (!restoredRef.current) {
      return;
    }
    if (draftHasContent(values, submitter)) {
      window.localStorage.setItem(
        INTAKE_DRAFT_STORAGE_KEY,
        serializeDraft(values, submitter, new Date().toISOString()),
      );
    }
  }, [values, submitter]);

  function setField(name: string, value: string) {
    setValues((current) => ({ ...current, [name]: value }));
  }

  async function handleExtract() {
    if (clientContext?.invoice_upload.available === false) {
      setExtractionNotice('Invoice upload is unavailable until Google Drive datastore setup is complete for this client.');
      return;
    }
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setExtractionNotice('Choose a document first, then run extraction.');
      return;
    }
    setExtracting(true);
    setError(null);
    setExtractionNotice(null);
    try {
      const formData = new FormData();
      formData.append('intent', INTAKE_INTENT);
      formData.append('file', file);
      const preview = await extractPreview(formData);
      const application = applyExtractedFields(values, preview.fields);
      setValues(application.values);
      setFlaggedFields(application.flagged);
      const populatedNote =
        application.populated.length > 0
          ? `Populated ${application.populated.length} field(s) from the document.`
          : 'No empty fields could be populated from the document.';
      const flaggedNote =
        application.flagged.length > 0
          ? ` ${application.flagged.length} field(s) need your attention.`
          : '';
      setExtractionNotice(populatedNote + flaggedNote);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Extraction failed');
    } finally {
      setExtracting(false);
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const missing = missingRequiredFields(values, submitter);
    if (missing.length > 0) {
      setError(`Required before submitting: ${missing.join(', ')}`);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('submitter', submitter.trim());
      formData.append('intent', INTAKE_INTENT);
      formData.append('fields', JSON.stringify(buildSubmissionFields(values)));
      const file = fileInputRef.current?.files?.[0];
      if (file && clientContext?.invoice_upload.available === false) {
        setError('Invoice upload is unavailable until Google Drive datastore setup is complete for this client.');
        setSubmitting(false);
        return;
      }
      if (file) {
        formData.append('file', file);
      }
      const result = await submitIntakeForm(formData);
      setSubmittedRunId(result.workflow_run.id);
      setValues(emptyIntakeForm());
      setSubmitter('');
      setFlaggedFields([]);
      setDraftNotice(null);
      window.localStorage.removeItem(INTAKE_DRAFT_STORAGE_KEY);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel intake-form-panel" aria-labelledby="intake-form-title">
      <h2 id="intake-form-title">CoachCW client intake</h2>
      <p className="intake-draft-note">
        Drafts save automatically to this browser only — they are not stored on our servers. Clearing
        browser data deletes your draft.
      </p>
      {draftNotice ? <p className="session-status">{draftNotice}</p> : null}
      {submittedRunId ? (
        <p className="session-status">
          Submitted — your details are with the CoachCW team for review (reference {submittedRunId}).
        </p>
      ) : null}
      {error ? <p className="session-error">{error}</p> : null}
      {clientContext?.invoice_upload.available === false ? (
        <p className="session-error">
          Invoice uploads are not available yet. Ask your SimpleTS workspace admin to finish Google Drive datastore setup for this client before attaching invoices.
        </p>
      ) : null}

      <form onSubmit={handleSubmit}>
        <label>
          Your name
          <input
            className="form-control"
            value={submitter}
            onChange={(event) => setSubmitter(event.target.value)}
            required
          />
        </label>

        <fieldset className="intake-upload">
          <legend>Supporting document (optional)</legend>
          <p>Upload an invoice, ATO notice, or ID document and we will pre-fill matching fields.</p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp,.txt"
            aria-label="Supporting document"
            disabled={clientContext?.invoice_upload.available === false}
          />
          <button type="button" onClick={handleExtract} disabled={extracting || submitting || clientContext?.invoice_upload.available === false}>
            {extracting ? 'Extracting… this can take up to 15 seconds' : 'Extract details from document'}
          </button>
          {extractionNotice ? <p className="session-status">{extractionNotice}</p> : null}
        </fieldset>

        {intakeSections().map((section) => (
          <fieldset key={section}>
            <legend>{section}</legend>
            {INTAKE_FIELDS.filter((field) => field.section === section).map((field) => (
              <label key={field.name} className={flaggedFields.includes(field.name) ? 'field-flagged' : undefined}>
                {field.label}
                {field.required ? ' *' : ''}
                {field.type === 'textarea' ? (
                  <textarea
                    className="form-control"
                    value={values[field.name] ?? ''}
                    onChange={(event) => setField(field.name, event.target.value)}
                    rows={2}
                  />
                ) : (
                  <input
                    className="form-control"
                    type={field.type}
                    value={values[field.name] ?? ''}
                    onChange={(event) => setField(field.name, event.target.value)}
                  />
                )}
                {flaggedFields.includes(field.name) ? (
                  <small className="field-flag-note">Check this value — extraction was uncertain.</small>
                ) : null}
              </label>
            ))}
          </fieldset>
        ))}

        <button type="submit" disabled={submitting || extracting}>
          {submitting ? 'Submitting…' : 'Submit to CoachCW'}
        </button>
      </form>
    </section>
  );
}
