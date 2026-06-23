import assert from 'node:assert/strict';
import { buildInvoiceImportFormData, canImportInvoice, searchInvoiceClients } from './clientInvoiceImportModel.ts';

const file = new File(['invoice'], 'invoice.pdf', { type: 'application/pdf' });
const clients = [
  { id: 'alpha', name: 'Alpha Advisory', email: 'payables@alpha.example' },
  { id: 'beta', name: 'Beta Builders', email: 'accounts@beta.example' },
];

assert.equal(canImportInvoice({ client: clients[0], file }), true);
assert.equal(canImportInvoice({ client: null, file }), false);
assert.equal(canImportInvoice({ client: clients[0], file: null }), false);
assert.deepEqual(searchInvoiceClients('pay alpha', clients).map((client) => client.id), ['alpha']);
assert.deepEqual(searchInvoiceClients('builder', clients).map((client) => client.id), ['beta']);

const formData = buildInvoiceImportFormData({ client: clients[0], file });
assert.equal(formData.get('intent'), 'invoice');
assert.equal(formData.get('uploader'), 'Alpha Advisory');
assert.equal(formData.get('file'), file);
assert.throws(() => buildInvoiceImportFormData({ client: null, file }), /client is required/);
assert.throws(() => buildInvoiceImportFormData({ client: clients[0], file: null }), /invoice file is required/);

console.log('clientInvoiceImportModel tests passed');
