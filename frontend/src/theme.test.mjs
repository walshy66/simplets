import assert from 'node:assert/strict';

import { THEME_STORAGE_KEY, resolveInitialTheme } from './theme.ts';

// A valid stored preference always wins over the system preference.
assert.equal(resolveInitialTheme('dark', false), 'dark');
assert.equal(resolveInitialTheme('light', true), 'light');

// With no (or an invalid) stored preference, fall back to the system signal.
assert.equal(resolveInitialTheme(null, true), 'dark');
assert.equal(resolveInitialTheme(null, false), 'light');
assert.equal(resolveInitialTheme('bogus', true), 'dark');
assert.equal(resolveInitialTheme('', false), 'light');

assert.equal(THEME_STORAGE_KEY, 'simplets.theme');

console.log('theme tests passed');
