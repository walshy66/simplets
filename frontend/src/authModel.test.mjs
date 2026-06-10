import assert from 'node:assert/strict';

import {
  DEFAULT_DEV_USER,
  bearerAuthHeaders,
  devAuthHeaders,
  resolveAuthMode,
  sanitizeDevUserId,
} from './authModel.ts';

// Mode selection: Clerk only when a publishable key is configured.
assert.equal(resolveAuthMode('pk_test_abc123'), 'clerk');
assert.equal(resolveAuthMode(''), 'dev');
assert.equal(resolveAuthMode('   '), 'dev');
assert.equal(resolveAuthMode(undefined), 'dev');
assert.equal(resolveAuthMode(null), 'dev');

// Dev identity falls back to the default named user, never an empty identity.
assert.equal(sanitizeDevUserId('  rita-reviewer '), 'rita-reviewer');
assert.equal(sanitizeDevUserId(''), DEFAULT_DEV_USER);
assert.equal(sanitizeDevUserId(null), DEFAULT_DEV_USER);

// Header shapes match what the backend expects in each mode.
assert.deepEqual(devAuthHeaders('rita-reviewer'), { 'X-STS-User': 'rita-reviewer' });
assert.deepEqual(devAuthHeaders(''), { 'X-STS-User': DEFAULT_DEV_USER });
assert.deepEqual(bearerAuthHeaders('jwt-token'), { Authorization: 'Bearer jwt-token' });
assert.deepEqual(bearerAuthHeaders(''), {});
assert.deepEqual(bearerAuthHeaders(null), {});

console.log('authModel tests passed');
