import { useEffect, useMemo, useState } from 'react';
import { PORTAL_FORMS } from '../dashboardModel';
import {
  BLANK_FORM_TEMPLATE,
  FIELD_TYPE_LABELS,
  PROTOTYPE_FORM_TEMPLATES,
  PrototypeFormField,
  PrototypeFormTemplate,
  canPublishForm,
  cloneTemplate,
  confirmAllMappings,
  connectorNames,
  fieldsNeedingMappingReview,
  moveField,
} from '../formEditorModel';
import IntakeFormPanel from './IntakeFormPanel';

function TemplatePicker({ onChoose }: { onChoose: (template: PrototypeFormTemplate) => void }) {
  return (
    <section className="panel form-editor-template-panel" aria-labelledby="form-editor-template-title">
      <div className="form-editor-header-row">
        <div>
          <p className="eyebrow">Form editor prototype</p>
          <h2 id="form-editor-template-title">Create a connector-aware form</h2>
          <p>Start from a smart template or a blank draft. Mock mappings show how SimpleTS will route fields to compatible connector destinations.</p>
        </div>
        <span className="sts-coming-soon-badge">Mock data</span>
      </div>
      <div className="form-template-grid">
        {PROTOTYPE_FORM_TEMPLATES.map((template) => (
          <button key={template.id} type="button" className="form-template-card" onClick={() => onChoose(template)}>
            <strong>{template.name}</strong>
            <span>{template.description}</span>
            <small>Xero + HubSpot suggested mappings preloaded</small>
          </button>
        ))}
        <button type="button" className="form-template-card form-template-card-secondary" onClick={() => onChoose(BLANK_FORM_TEMPLATE)}>
          <strong>Start blank</strong>
          <span>Add your own fields and mappings from scratch.</span>
          <small>Fields can be added after backend contracts are wired.</small>
        </button>
      </div>
    </section>
  );
}

function FieldPreview({ field }: { field: PrototypeFormField }) {
  if (field.type === 'longText') return <textarea className="form-control" disabled placeholder="Client answer" />;
  if (field.type === 'dropdown') {
    return (
      <select className="form-control" disabled>
        <option>{field.options?.[0] ?? 'Select an option'}</option>
      </select>
    );
  }
  if (field.type === 'multiSelect') return <div className="form-editor-placeholder">Multiple options</div>;
  if (field.type === 'yesNo') return <div className="form-editor-placeholder">Yes / No</div>;
  if (field.type === 'addressGroup') return <div className="form-editor-placeholder">Address line, city, state, postcode, country</div>;
  if (field.type === 'file') return <div className="form-editor-placeholder">File upload placeholder</div>;
  return <input className="form-control" disabled placeholder={FIELD_TYPE_LABELS[field.type]} />;
}

function MappingPanel({ field, onClose }: { field: PrototypeFormField; onClose: () => void }) {
  return (
    <aside className="form-mapping-panel" aria-label="Connector mapping details">
      <div className="form-editor-header-row">
        <div>
          <p className="eyebrow">Selected field</p>
          <h3>{field.label}</h3>
        </div>
        <button type="button" onClick={onClose}>Close</button>
      </div>
      <dl className="form-field-meta">
        <div><dt>Type</dt><dd>{FIELD_TYPE_LABELS[field.type]}</dd></div>
        <div><dt>Required</dt><dd>{field.required ? 'Yes' : 'No'}</dd></div>
        <div><dt>Section</dt><dd>{field.section}</dd></div>
      </dl>
      {field.helpText ? <p className="muted">{field.helpText}</p> : null}
      <h4>Compatible connector destinations</h4>
      <div className="mapping-list">
        {field.mappings.map((mapping) => (
          <article key={`${mapping.connectorId}-${mapping.fieldName}`} className="mapping-card">
            <div>
              <strong>{mapping.connectorName}</strong>
              <span>{mapping.objectName} → {mapping.fieldName}</span>
            </div>
            <span className={mapping.confirmed ? 'mapping-confirmed' : 'mapping-needs-review'}>
              {mapping.confirmed ? 'Confirmed' : 'Needs review'}
            </span>
          </article>
        ))}
      </div>
      <p className="muted">Future modal: add/remove connector mappings and only offer fields compatible with each app API.</p>
    </aside>
  );
}

function FormEditor({ initialTemplate, onBack }: { initialTemplate: PrototypeFormTemplate; onBack: () => void }) {
  const [templateName] = useState(initialTemplate.name);
  const [fields, setFields] = useState(() => cloneTemplate(initialTemplate).fields);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(fields[0]?.id ?? null);
  const [publishedVersion, setPublishedVersion] = useState<number | null>(null);
  const needsReview = fieldsNeedingMappingReview(fields);
  const selectedField = fields.find((field) => field.id === selectedFieldId) ?? fields[0];
  const fieldsBySection = useMemo(() => {
    return fields.reduce<Record<string, PrototypeFormField[]>>((sections, field) => {
      sections[field.section] = [...(sections[field.section] ?? []), field];
      return sections;
    }, {});
  }, [fields]);

  function moveAndKeepSelection(fieldId: string, direction: 'up' | 'down') {
    setFields((current) => moveField(current, fieldId, direction));
    setSelectedFieldId(fieldId);
  }

  function confirmMappings() {
    setFields((current) => confirmAllMappings(current));
  }

  function publishDraft() {
    if (!canPublishForm(fields)) return;
    setPublishedVersion((current) => (current ?? 0) + 1);
  }

  return (
    <div className="form-editor-shell">
      <section className="panel form-editor-topbar" aria-labelledby="form-editor-title">
        <button type="button" onClick={onBack}>← Forms</button>
        <div>
          <p className="eyebrow">Draft editor</p>
          <h2 id="form-editor-title">{templateName}</h2>
          <p>Stable public link: <code>/forms/new-client</code> · Published version: {publishedVersion ? `v${publishedVersion}` : 'not published'}</p>
        </div>
        <div className="form-editor-actions">
          <span className={needsReview.length ? 'mapping-needs-review' : 'mapping-confirmed'}>
            {needsReview.length ? `${needsReview.length} fields need mapping review` : 'Mappings confirmed'}
          </span>
          <button type="button" onClick={confirmMappings} disabled={!needsReview.length}>Confirm form mappings</button>
          <button type="button" className="button-primary" onClick={publishDraft} disabled={!canPublishForm(fields)}>Publish draft</button>
        </div>
      </section>

      <div className="form-editor-workspace">
        <section className="panel form-editor-canvas" aria-label="Form canvas">
          <div className="form-editor-canvas-title">
            <div>
              <h3>Client form canvas</h3>
              <p className="muted">Vertical form layout with up/down ordering. Click a field to review connector mappings.</p>
            </div>
            <button type="button" disabled>+ Add field</button>
          </div>
          {fields.length === 0 ? (
            <div className="form-editor-empty">Blank draft created. Field creation controls will be wired in the next slice.</div>
          ) : null}
          {Object.entries(fieldsBySection).map(([section, sectionFields]) => (
            <div key={section} className="form-editor-section">
              <h4>{section}</h4>
              {sectionFields.map((field) => {
                const globalIndex = fields.findIndex((candidate) => candidate.id === field.id);
                return (
                  <article key={field.id} className={selectedFieldId === field.id ? 'form-field-card form-field-card-selected' : 'form-field-card'}>
                    <button type="button" className="form-field-select" onClick={() => setSelectedFieldId(field.id)}>
                      <span>
                        <strong>{field.label}</strong>
                        {field.required ? <em>Required</em> : null}
                      </span>
                      <small>{FIELD_TYPE_LABELS[field.type]}</small>
                    </button>
                    <FieldPreview field={field} />
                    <div className="form-field-footer">
                      <div className="connector-chip-row">
                        {connectorNames(field).map((name) => <span key={name} className="connector-chip">{name}</span>)}
                      </div>
                      <div className="form-field-order-actions">
                        <button type="button" onClick={() => moveAndKeepSelection(field.id, 'up')} disabled={globalIndex === 0}>↑</button>
                        <button type="button" onClick={() => moveAndKeepSelection(field.id, 'down')} disabled={globalIndex === fields.length - 1}>↓</button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          ))}
        </section>
        {selectedField ? <MappingPanel field={selectedField} onClose={() => setSelectedFieldId(null)} /> : null}
      </div>
    </div>
  );
}

function templateForPath(pathname: string): PrototypeFormTemplate | null {
  if (pathname.startsWith('/forms/new') || pathname.startsWith('/forms/new-client/edit')) {
    return PROTOTYPE_FORM_TEMPLATES[0];
  }
  return null;
}

export default function FormsPage() {
  const [openFormId, setOpenFormId] = useState<string | null>(null);
  const [editorTemplate, setEditorTemplate] = useState<PrototypeFormTemplate | null>(() => templateForPath(window.location.pathname));

  useEffect(() => {
    const onPopState = () => setEditorTemplate(templateForPath(window.location.pathname));
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  function openEditor(template: PrototypeFormTemplate) {
    const path = template.id === 'blank-form' ? '/forms/new' : '/forms/new-client/edit';
    window.history.pushState(null, '', path);
    setEditorTemplate(template);
  }

  function closeEditor() {
    window.history.pushState(null, '', '/forms');
    setEditorTemplate(null);
  }

  if (editorTemplate) {
    return <FormEditor initialTemplate={editorTemplate} onBack={closeEditor} />;
  }

  return (
    <div>
      <TemplatePicker onChoose={openEditor} />
      <section className="panel" aria-labelledby="forms-title">
        <h2 id="forms-title">Your client forms</h2>
        <p>Forms your clients fill out. Submissions land in the review queue for approval.</p>
        <div className="forms-list">
          {PORTAL_FORMS.map((form) => (
            <button
              key={form.id}
              type="button"
              className={`forms-list-card${form.status === 'sample' ? ' forms-list-sample' : ''}`}
              onClick={() => form.status === 'live' && setOpenFormId(openFormId === form.id ? null : form.id)}
              disabled={form.status === 'sample'}
            >
              <strong>{form.name}</strong>
              <span className={`form-status form-status-${form.status}`}>
                {form.status === 'live' ? 'Live' : 'Sample'}
              </span>
              <small>{form.description}</small>
            </button>
          ))}
        </div>
      </section>
      {openFormId === 'coachcw-client-intake' ? <IntakeFormPanel /> : null}
    </div>
  );
}
