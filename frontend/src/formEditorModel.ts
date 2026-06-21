export type ConnectorId = 'xero' | 'hubspot';

export type FormFieldType =
  | 'text'
  | 'longText'
  | 'email'
  | 'phone'
  | 'url'
  | 'number'
  | 'dropdown'
  | 'multiSelect'
  | 'yesNo'
  | 'date'
  | 'currency'
  | 'file'
  | 'addressGroup';

export type ConnectorMapping = {
  connectorId: ConnectorId;
  connectorName: string;
  objectName: string;
  fieldName: string;
  confidence: 'high' | 'medium' | 'manual';
  confirmed: boolean;
};

export type PrototypeFormField = {
  id: string;
  label: string;
  type: FormFieldType;
  required: boolean;
  section: string;
  helpText?: string;
  options?: string[];
  mappings: ConnectorMapping[];
};

export type PrototypeFormTemplate = {
  id: string;
  name: string;
  description: string;
  fields: PrototypeFormField[];
};

export const FIELD_TYPE_LABELS: Record<FormFieldType, string> = {
  text: 'Text',
  longText: 'Long text',
  email: 'Email',
  phone: 'Phone',
  url: 'URL',
  number: 'Number',
  dropdown: 'Dropdown',
  multiSelect: 'Multi-select',
  yesNo: 'Yes/No',
  date: 'Date',
  currency: 'Currency',
  file: 'File upload',
  addressGroup: 'Address group',
};

const xero = (fieldName: string, objectName = 'Contact'): ConnectorMapping => ({
  connectorId: 'xero',
  connectorName: 'Xero',
  objectName,
  fieldName,
  confidence: 'high',
  confirmed: false,
});

const hubspot = (fieldName: string, objectName = 'Company'): ConnectorMapping => ({
  connectorId: 'hubspot',
  connectorName: 'HubSpot',
  objectName,
  fieldName,
  confidence: 'high',
  confirmed: false,
});

export const NEW_CLIENT_TEMPLATE: PrototypeFormTemplate = {
  id: 'new-client-form',
  name: 'New Client Form',
  description: 'Business, contact, accounting, and CRM details for onboarding a new client.',
  fields: [
    {
      id: 'business-name',
      label: 'Business name',
      type: 'text',
      required: true,
      section: 'Business details',
      mappings: [xero('Name'), hubspot('name')],
    },
    {
      id: 'abn-tax-id',
      label: 'ABN / tax identifier',
      type: 'text',
      required: true,
      section: 'Business details',
      helpText: 'Use validation metadata later for regional business identifiers.',
      mappings: [xero('TaxNumber'), hubspot('abn_tax_identifier', 'Company custom property')],
    },
    {
      id: 'company-number',
      label: 'Company number / ACN',
      type: 'text',
      required: false,
      section: 'Business details',
      mappings: [xero('CompanyNumber'), hubspot('company_number', 'Company custom property')],
    },
    {
      id: 'website',
      label: 'Website',
      type: 'url',
      required: false,
      section: 'Business details',
      mappings: [xero('Website'), hubspot('domain')],
    },
    {
      id: 'contact-first-name',
      label: 'Main contact first name',
      type: 'text',
      required: true,
      section: 'Main contact',
      mappings: [xero('FirstName'), hubspot('firstname', 'Contact')],
    },
    {
      id: 'contact-last-name',
      label: 'Main contact last name',
      type: 'text',
      required: true,
      section: 'Main contact',
      mappings: [xero('LastName'), hubspot('lastname', 'Contact')],
    },
    {
      id: 'contact-email',
      label: 'Main contact email',
      type: 'email',
      required: true,
      section: 'Main contact',
      mappings: [xero('EmailAddress'), hubspot('email', 'Contact')],
    },
    {
      id: 'contact-phone',
      label: 'Main contact phone',
      type: 'phone',
      required: false,
      section: 'Main contact',
      mappings: [xero('Phones[].PhoneNumber'), hubspot('phone', 'Contact')],
    },
    {
      id: 'job-title',
      label: 'Job title',
      type: 'text',
      required: false,
      section: 'Main contact',
      mappings: [hubspot('jobtitle', 'Contact')],
    },
    {
      id: 'street-address',
      label: 'Street address',
      type: 'addressGroup',
      required: false,
      section: 'Address',
      mappings: [xero('Addresses[STREET]'), hubspot('address')],
    },
    {
      id: 'is-customer',
      label: 'Create as customer?',
      type: 'yesNo',
      required: true,
      section: 'Accounting setup',
      mappings: [xero('IsCustomer')],
    },
    {
      id: 'is-supplier',
      label: 'Create as supplier?',
      type: 'yesNo',
      required: false,
      section: 'Accounting setup',
      mappings: [xero('IsSupplier')],
    },
    {
      id: 'preferred-currency',
      label: 'Preferred currency',
      type: 'dropdown',
      required: false,
      section: 'Accounting setup',
      options: ['AUD', 'NZD', 'USD', 'GBP'],
      mappings: [xero('DefaultCurrency')],
    },
    {
      id: 'payment-terms',
      label: 'Payment terms',
      type: 'dropdown',
      required: false,
      section: 'Accounting setup',
      options: ['7 days', '14 days', '30 days', 'End of month'],
      mappings: [xero('PaymentTerms')],
    },
    {
      id: 'lifecycle-stage',
      label: 'Lifecycle stage',
      type: 'dropdown',
      required: false,
      section: 'CRM details',
      options: ['Subscriber', 'Lead', 'Marketing qualified lead', 'Sales qualified lead', 'Opportunity', 'Customer'],
      mappings: [hubspot('lifecyclestage')],
    },
    {
      id: 'industry',
      label: 'Industry',
      type: 'dropdown',
      required: false,
      section: 'CRM details',
      options: ['Accounting', 'Construction', 'Consulting', 'Healthcare', 'Retail', 'Technology'],
      mappings: [hubspot('industry')],
    },
    {
      id: 'number-of-assets',
      label: 'Number of assets',
      type: 'number',
      required: false,
      section: 'CRM details',
      mappings: [hubspot('number_of_assets', 'Company custom property')],
    },
    {
      id: 'notes',
      label: 'Notes/context',
      type: 'longText',
      required: false,
      section: 'CRM details',
      mappings: [hubspot('onboarding_notes', 'Company custom property')],
    },
  ],
};

export const PROTOTYPE_FORM_TEMPLATES: PrototypeFormTemplate[] = [NEW_CLIENT_TEMPLATE];

export const BLANK_FORM_TEMPLATE: PrototypeFormTemplate = {
  id: 'blank-form',
  name: 'Blank form',
  description: 'Start with no fields and add your own connector-aware intake fields.',
  fields: [],
};

export function cloneTemplate(template: PrototypeFormTemplate): PrototypeFormTemplate {
  return JSON.parse(JSON.stringify(template)) as PrototypeFormTemplate;
}

export function connectorNames(field: PrototypeFormField): string[] {
  return Array.from(new Set(field.mappings.map((mapping) => mapping.connectorName)));
}

export function fieldsNeedingMappingReview(fields: PrototypeFormField[]): PrototypeFormField[] {
  return fields.filter((field) => field.mappings.some((mapping) => !mapping.confirmed));
}

export function canPublishForm(fields: PrototypeFormField[]): boolean {
  return fields.length > 0 && fieldsNeedingMappingReview(fields).length === 0;
}

export function confirmAllMappings(fields: PrototypeFormField[]): PrototypeFormField[] {
  return fields.map((field) => ({
    ...field,
    mappings: field.mappings.map((mapping) => ({ ...mapping, confirmed: true })),
  }));
}

export function moveField(fields: PrototypeFormField[], fieldId: string, direction: 'up' | 'down'): PrototypeFormField[] {
  const index = fields.findIndex((field) => field.id === fieldId);
  if (index === -1) return fields;
  const targetIndex = direction === 'up' ? index - 1 : index + 1;
  if (targetIndex < 0 || targetIndex >= fields.length) return fields;
  const next = [...fields];
  [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
  return next;
}
