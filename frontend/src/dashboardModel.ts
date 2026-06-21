export type PortalRoute =
  | 'dashboard'
  | 'forms'
  | 'workflows'
  | 'review'
  | 'process-maps'
  | 'clients'
  | 'settings';

const ROUTE_PATHS: Record<string, PortalRoute> = {
  '': 'dashboard',
  '/': 'dashboard',
  '/forms': 'forms',
  '/workflows': 'workflows',
  '/review': 'review',
  '/process-maps': 'process-maps',
  '/clients': 'clients',
  '/settings': 'settings',
};

export function parseRoute(pathname: string): PortalRoute {
  const normalized = pathname.replace(/\/+$/, '') || '/';
  if (normalized.startsWith('/process-maps/')) {
    return 'process-maps';
  }
  if (normalized.startsWith('/forms/')) {
    return 'forms';
  }
  return ROUTE_PATHS[normalized] ?? 'dashboard';
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

// No client backend yet — the Clients tile shows a placeholder count.
export const DUMMY_CLIENT_COUNT = 18;

// Workflow count is dummied until the canvas backend exposes a flow list to STS.
export const DUMMY_WORKFLOW_COUNT = 3;

/** Time-of-day greeting for the dashboard hero. */
export function greeting(date: Date = new Date()): string {
  const hour = date.getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

/** Compact "x ago" label for review-queue timestamps. */
export function relativeTime(from: Date, now: Date = new Date()): string {
  const ms = now.getTime() - from.getTime();
  const minutes = Math.floor(ms / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Up to two uppercase initials for an avatar, from a name or filename. */
export function initials(label: string): string {
  const parts = label.trim().split(/[\s_\-.]+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
