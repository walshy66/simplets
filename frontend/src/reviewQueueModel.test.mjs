import assert from 'node:assert/strict';
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
  invoiceReviewStatus,
  parseEditableFields,
} from './reviewQueueModel.ts';

assert.equal(canSaveExtractedFields('{"summary":"Edited"}'), true);
assert.equal(canSaveExtractedFields('not json'), false);
assert.deepEqual(parseEditableFields('{"summary":"Edited","count":2}'), { summary: 'Edited', count: 2 });
assert.throws(() => parseEditableFields('[]'), /must be a JSON object/);
assert.throws(() => parseEditableFields('not json'), /valid JSON/);

assert.equal(canApproveReviewRun({ hasOpenedExtractedDataScreen: false, fieldsAreValid: true }), false);
assert.equal(canApproveReviewRun({ hasOpenedExtractedDataScreen: true, fieldsAreValid: false }), false);
assert.equal(canApproveReviewRun({ hasOpenedExtractedDataScreen: true, fieldsAreValid: true }), true);

assert.equal(formatSourcePreview({ available: true, content: 'Original text', reason: null }), 'Original text');
assert.equal(
  formatSourcePreview({ available: false, content: null, reason: 'document no longer retained' }),
  'Source unavailable: document no longer retained',
);

// Approval outcome messaging: success purges, failure retains with reasons.
const success = formatApprovalOutcome({
  all_succeeded: true,
  destination_pushes: [
    { provider: 'mock', status: 'succeeded', destination_record_id: 'mock-destination-run-1', error_message: null },
  ],
});
assert.ok(success.includes('purged from SimpleTS'));
assert.ok(success.includes('mock: mock-destination-run-1'));

const failure = formatApprovalOutcome({
  all_succeeded: false,
  destination_pushes: [
    { provider: 'mock', status: 'succeeded', destination_record_id: 'mock-1', error_message: null },
    { provider: 'hubspot', status: 'failed', destination_record_id: null, error_message: 'hubspot rejected the record: 500' },
  ],
});
assert.ok(failure.includes('data is retained'));
assert.ok(failure.includes('hubspot rejected the record: 500'));

// Flagged-field helpers read the _extraction metadata.
const extracted = {
  total: null,
  issuer: 'Acme',
  _extraction: {
    flagged_fields: ['total'],
    field_details: { total: { flag_reason: 'required value missing from document' } },
  },
};
assert.deepEqual(flaggedFieldNames(extracted), ['total']);
assert.equal(flagReason(extracted, 'total'), 'required value missing from document');
assert.equal(flagReason(extracted, 'issuer'), null);
assert.deepEqual(flaggedFieldNames(null), []);
assert.deepEqual(flaggedFieldNames({ plain: 'fields' }), []);

assert.equal(hasFailedPushes([{ provider: 'mock', status: 'succeeded', destination_record_id: null, error_message: null }]), false);
assert.equal(hasFailedPushes([{ provider: 'hubspot', status: 'failed', destination_record_id: null, error_message: 'x' }]), true);

assert.deepEqual(
  getImproveExtractionControl({
    extractedFields: { invoice_date: null, _extraction: { flagged_fields: ['invoice_date'] } },
    gate: { feature_enabled: true, subscription_enabled: true, permission_allowed: true, action_enabled: false },
  }),
  {
    visible: true,
    enabled: false,
    label: 'Improve extraction',
    message: 'Enhanced extraction is not enabled yet. No workspace usage allowance/usage units will be consumed.',
  },
);
assert.equal(
  getImproveExtractionControl({
    extractedFields: {
      invoice_number: 'INV-1',
      vendor_name: 'Acme',
      invoice_date: '2026-06-01',
      due_date: '2026-06-30',
      total_amount: 100,
      currency: 'AUD',
      _extraction: { field_details: { invoice_number: { confidence: 'high' } } },
    },
    gate: { feature_enabled: true, subscription_enabled: true, permission_allowed: true, action_enabled: false },
  }).visible,
  false,
);
assert.match(
  getImproveExtractionControl({
    extractedFields: { invoice_date: null },
    gate: { feature_enabled: false, subscription_enabled: true, permission_allowed: true, action_enabled: false },
  }).message,
  /workspace usage allowance\/usage units/i,
);
assert.equal(
  getImproveExtractionControl({
    extractedFields: { invoice_date: null },
    gate: { feature_enabled: true, subscription_enabled: true, permission_allowed: true, action_enabled: true },
  }).enabled,
  true,
);

assert.equal(invoiceReviewStatus({ review_status: 'pending', document: { deletion_status: 'retained' } }), 'Needs review');
assert.equal(invoiceReviewStatus({ review_status: 'reviewed', document: { deletion_status: 'retained' } }), 'Reviewed');
assert.equal(invoiceReviewStatus({ review_status: 'approved', document: { deletion_status: 'retained' } }), 'Reviewed');
assert.equal(invoiceReviewStatus({ review_status: 'approved', document: { deletion_status: 'deleted' } }), 'Purged');

const rows = invoiceFieldRows({
  invoice_number: 'INV-100',
  vendor_name: 'Acme Supplies',
  invoice_date: null,
  due_date: '2026-07-01',
  total_amount: 1100,
  currency: 'AUD',
  _extraction: {
    flagged_fields: ['invoice_date'],
    field_details: {
      invoice_number: { source: 'document text', confidence: 'high' },
      invoice_date: { source: null, confidence: 'missing', flag_reason: 'not found in document' },
    },
  },
});
assert.deepEqual(rows.map((row) => row.key), ['invoice_number', 'vendor_name', 'invoice_date', 'due_date', 'total_amount', 'currency']);
assert.equal(rows[0].label, 'Invoice number');
assert.equal(rows[0].displayValue, 'INV-100');
assert.equal(rows[0].provenanceLabel, 'document text · high confidence');
assert.equal(rows[2].isMissingOrUncertain, true);
assert.equal(rows[2].displayValue, 'Missing');
assert.equal(rows[2].provenanceLabel, 'Provenance unavailable · missing confidence');
assert.equal(rows.some((row) => row.key === 'line_items'), false);

console.log('reviewQueueModel tests passed');
