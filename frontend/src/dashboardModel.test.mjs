import assert from 'node:assert/strict';

import {
  PORTAL_FORMS,
  formatRenewalDate,
  liveFormCount,
  parseRoute,
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
assert.equal(parseRoute('/workflows'), 'workflows');
assert.equal(parseRoute('/review'), 'review');
assert.equal(parseRoute('/unknown'), 'dashboard');
for (const route of ['dashboard', 'forms', 'workflows', 'review']) {
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

console.log('dashboardModel tests passed');
