export type AuthMode = 'clerk' | 'dev';

export const DEV_USER_STORAGE_KEY = 'simplets.devUserId';
export const DEFAULT_DEV_USER = 'platform-admin';

export function resolveAuthMode(clerkPublishableKey: string | undefined | null): AuthMode {
  return clerkPublishableKey && clerkPublishableKey.trim() ? 'clerk' : 'dev';
}

export function sanitizeDevUserId(raw: string | null | undefined): string {
  const clean = (raw ?? '').trim();
  return clean || DEFAULT_DEV_USER;
}

export function devAuthHeaders(userId: string): Record<string, string> {
  return { 'X-STS-User': sanitizeDevUserId(userId) };
}

export function bearerAuthHeaders(token: string | null | undefined): Record<string, string> {
  const clean = (token ?? '').trim();
  return clean ? { Authorization: `Bearer ${clean}` } : {};
}
