import assert from 'node:assert/strict';

import {
  BLANK_FORM_TEMPLATE,
  FIELD_TYPE_LABELS,
  NEW_CLIENT_TEMPLATE,
  canPublishForm,
  cloneTemplate,
  confirmAllMappings,
  connectorNames,
  fieldsNeedingMappingReview,
  moveField,
} from './formEditorModel.ts';

assert.equal(NEW_CLIENT_TEMPLATE.name, 'New Client Form');
assert.ok(NEW_CLIENT_TEMPLATE.fields.length >= 12);
assert.ok(NEW_CLIENT_TEMPLATE.fields.some((field) => field.id === 'business-name'));
assert.ok(NEW_CLIENT_TEMPLATE.fields.some((field) => field.mappings.some((mapping) => mapping.connectorId === 'xero')));
assert.ok(NEW_CLIENT_TEMPLATE.fields.some((field) => field.mappings.some((mapping) => mapping.connectorId === 'hubspot')));
assert.equal(FIELD_TYPE_LABELS.email, 'Email');

const businessName = NEW_CLIENT_TEMPLATE.fields.find((field) => field.id === 'business-name');
assert.deepEqual(connectorNames(businessName), ['Xero', 'HubSpot']);
assert.ok(fieldsNeedingMappingReview(NEW_CLIENT_TEMPLATE.fields).length > 0);
assert.equal(canPublishForm(NEW_CLIENT_TEMPLATE.fields), false);

const confirmed = confirmAllMappings(NEW_CLIENT_TEMPLATE.fields);
assert.equal(fieldsNeedingMappingReview(confirmed).length, 0);
assert.equal(canPublishForm(confirmed), true);
assert.equal(canPublishForm(BLANK_FORM_TEMPLATE.fields), false);

const cloned = cloneTemplate(NEW_CLIENT_TEMPLATE);
cloned.fields[0].label = 'Mutated';
assert.notEqual(NEW_CLIENT_TEMPLATE.fields[0].label, 'Mutated');

const movedDown = moveField(NEW_CLIENT_TEMPLATE.fields, NEW_CLIENT_TEMPLATE.fields[0].id, 'down');
assert.equal(movedDown[1].id, NEW_CLIENT_TEMPLATE.fields[0].id);
const movedUp = moveField(movedDown, NEW_CLIENT_TEMPLATE.fields[0].id, 'up');
assert.equal(movedUp[0].id, NEW_CLIENT_TEMPLATE.fields[0].id);
assert.equal(moveField(NEW_CLIENT_TEMPLATE.fields, 'missing', 'up'), NEW_CLIENT_TEMPLATE.fields);

console.log('formEditorModel tests passed');
