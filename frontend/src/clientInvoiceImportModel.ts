export type ImportClient = {
  id: string;
  name: string;
  email?: string;
};

export type InvoiceImportDraft = {
  client: ImportClient | null;
  file: File | null;
};

export const DEMO_INVOICE_CLIENTS: ImportClient[] = [
  { id: 'acme-plumbing', name: 'Acme Plumbing', email: 'accounts@acme.example' },
  { id: 'bright-books', name: 'Bright Books Pty Ltd', email: 'payables@bright.example' },
  { id: 'coachcw', name: 'CoachCW', email: 'admin@coachcw.example' },
  { id: 'regroup-solutions', name: 'ReGroup Solutions', email: 'ops@regroup.example' },
];

export function searchInvoiceClients(query: string, clients: ImportClient[] = DEMO_INVOICE_CLIENTS): ImportClient[] {
  const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return clients.slice(0, 6);
  return clients
    .map((client) => {
      const haystack = `${client.name} ${client.email ?? ''}`.toLowerCase();
      const score = terms.reduce((total, term) => total + (haystack.includes(term) ? 1 : 0), 0);
      return { client, score };
    })
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.client.name.localeCompare(b.client.name))
    .map((entry) => entry.client)
    .slice(0, 6);
}

export function canImportInvoice(draft: InvoiceImportDraft): boolean {
  return Boolean(draft.client && draft.file);
}

export function buildInvoiceImportFormData(draft: InvoiceImportDraft): FormData {
  if (!draft.client) throw new Error('client is required');
  if (!draft.file) throw new Error('invoice file is required');
  const formData = new FormData();
  formData.append('intent', 'invoice');
  formData.append('uploader', draft.client.name);
  formData.append('file', draft.file);
  return formData;
}
