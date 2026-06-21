export type Theme = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'simplets.theme';

export const STS_PLATFORM_BRAND = {
  companyName: 'Simple Technology Solutions',
  productName: 'SimpleTS',
  tagline: 'Make Work Simple',
  colors: {
    midnightIndigo: '#150A32',
    digitalTeal: '#20B4C9',
    electricMint: '#15F5BA',
    white: '#FFFFFF',
  },
  fonts: {
    heading: 'Montserrat',
    body: 'Calibri',
  },
} as const;

/** A stored preference wins; otherwise fall back to the OS preference. */
export function resolveInitialTheme(stored: string | null, prefersDark: boolean): Theme {
  if (stored === 'light' || stored === 'dark') {
    return stored;
  }
  return prefersDark ? 'dark' : 'light';
}

export function systemPrefersDark(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  );
}

export function readStoredTheme(): string | null {
  try {
    return window.localStorage.getItem(THEME_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function persistTheme(theme: Theme): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    /* storage unavailable (private mode, etc.) — non-fatal */
  }
}

/** Reflect the theme on <html> so the [data-theme] CSS rules take effect. */
export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute('data-theme', theme);
}
