import assert from 'node:assert/strict';

import {
  PORTAL_FORMS,
  formatRenewalDate,
  greeting,
  initials,
  liveFormCount,
  parseRoute,
  relativeTime,
  routePath,
  usagePercent,
  usageRemaining,
  usageRenewalDate,
} from './dashboardModel.ts';

// Path routing round-trips and falls back to the dashboard.
assert.equal(parseRoute(''), 'dashboard');
assert.equal(parseRoute('/'), 'dashboard');
assert.equal(parseRoute('/forms'), 'forms');
assert.equal(parseRoute('/forms/'), 'forms');
assert.equal(parseRoute('/forms/new'), 'forms');
assert.equal(parseRoute('/forms/new-client/edit'), 'forms');
assert.equal(parseRoute('/workflows'), 'workflows');
assert.equal(parseRoute('/review'), 'review');
assert.equal(parseRoute('/process-maps'), 'process-maps');
assert.equal(parseRoute('/process-maps/map-1'), 'process-maps');
assert.equal(parseRoute('/clients'), 'clients');
assert.equal(parseRoute('/settings'), 'settings');
assert.equal(parseRoute('/unknown'), 'dashboard');
for (const route of ['dashboard', 'forms', 'workflows', 'review', 'process-maps', 'clients', 'settings']) {
  assert.equal(parseRoute(routePath(route)), route);
}

// Usage math clamps and never goes negative.
assert.equal(usagePercent({ used: 1240, limit: 5000 }), 25);
assert.equal(usagePercent({ used: 9999, limit: 5000 }), 100);
assert.equal(usagePercent({ used: 10, limit: 0 }), 0);
assert.equal(usageRemaining({ used: 1240, limit: 5000 }), 3760);
assert.equal(usageRemaining({ used: 9999, limit: 5000 }), 0);

// Renewal is the first of the next month, including year rollover.
const midMonth = usageRenewalDate(new Date(2026, 5, 11)); // 11 June 2026
assert.equal(midMonth.getFullYear(), 2026);
assert.equal(midMonth.getMonth(), 6);
assert.equal(midMonth.getDate(), 1);
const december = usageRenewalDate(new Date(2026, 11, 31));
assert.equal(december.getFullYear(), 2027);
assert.equal(december.getMonth(), 0);
assert.ok(formatRenewalDate(midMonth).includes('July'));
assert.ok(formatRenewalDate(midMonth).includes('2026'));

// One live form (the hardcoded CoachCW intake), samples don't count.
assert.equal(liveFormCount(PORTAL_FORMS), 1);
assert.ok(PORTAL_FORMS.some((form) => form.id === 'coachcw-client-intake' && form.status === 'live'));

// Greeting follows the local hour.
assert.equal(greeting(new Date(2026, 5, 16, 8, 0)), 'Good morning');
assert.equal(greeting(new Date(2026, 5, 16, 13, 0)), 'Good afternoon');
assert.equal(greeting(new Date(2026, 5, 16, 21, 0)), 'Good evening');

// Relative time buckets into just now / minutes / hours / days.
const base = new Date(2026, 5, 16, 12, 0, 0);
assert.equal(relativeTime(new Date(2026, 5, 16, 11, 59, 40), base), 'just now');
assert.equal(relativeTime(new Date(2026, 5, 16, 11, 45, 0), base), '15m ago');
assert.equal(relativeTime(new Date(2026, 5, 16, 10, 0, 0), base), '2h ago');
assert.equal(relativeTime(new Date(2026, 5, 14, 12, 0, 0), base), '2d ago');

// Initials take the first + last token, handle single tokens and separators.
assert.equal(initials('Riverside Physio'), 'RP');
assert.equal(initials('Bright Spark Tutors'), 'BT');
assert.equal(initials('intake.pdf'), 'IP');
assert.equal(initials('coachcw'), 'CO');
assert.equal(initials('  '), '?');

console.log('dashboardModel tests passed');
