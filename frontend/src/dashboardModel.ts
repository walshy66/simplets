export type PortalRoute = 'dashboard' | 'forms' | 'workflows' | 'review';

const ROUTE_PATHS: Record<string, PortalRoute> = {
  '': 'dashboard',
  '/': 'dashboard',
  '/forms': 'forms',
  '/workflows': 'workflows',
  '/review': 'review',
};

export function parseRoute(pathname: string): PortalRoute {
  return ROUTE_PATHS[pathname.replace(/\/+$/, '') || '/'] ?? 'dashboard';
}

export function routePath(route: PortalRoute): string {
  return route === 'dashboard' ? '/' : `/${route}`;
}

export type AiUsage = {
  used: number;
  limit: number;
};

// Placeholder until extraction metering lands — shape matches what the card renders.
export const DUMMY_AI_USAGE: AiUsage = { used: 1240, limit: 5000 };

export function usagePercent(usage: AiUsage): number {
  if (usage.limit <= 0) {
    return 0;
  }
  return Math.min(100, Math.max(0, Math.round((usage.used / usage.limit) * 100)));
}

export function usageRemaining(usage: AiUsage): number {
  return Math.max(0, usage.limit - usage.used);
}

/** Usage limits renew on the first of the next month. */
export function usageRenewalDate(from: Date): Date {
  return new Date(from.getFullYear(), from.getMonth() + 1, 1);
}

export function formatRenewalDate(date: Date): string {
  return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'long', year: 'numeric' });
}

export type FormSummary = {
  id: string;
  name: string;
  status: 'live' | 'sample';
  description: string;
};

// v1 has no form builder: the CoachCW intake form is the one live form.
// Samples illustrate what the list looks like as more forms are added.
export const PORTAL_FORMS: FormSummary[] = [
  {
    id: 'coachcw-client-intake',
    name: 'CoachCW client intake',
    status: 'live',
    description: 'Identity, business, ATO and engagement details for new clients.',
  },
  {
    id: 'sample-annual-review',
    name: 'Annual review questionnaire',
    status: 'sample',
    description: 'Sample — yearly client circumstances refresh.',
  },
  {
    id: 'sample-smsf-onboarding',
    name: 'SMSF onboarding',
    status: 'sample',
    description: 'Sample — self-managed super fund setup pack.',
  },
];

export function liveFormCount(forms: FormSummary[]): number {
  return forms.filter((form) => form.status === 'live').length;
}
