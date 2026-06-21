import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const css = readFileSync(new URL('./App.css', import.meta.url), 'utf8');
// The legacy session dashboard now lives behind VITE_ENABLE_AGENT_DASHBOARD.
const app = readFileSync(new URL('./components/AgentSessionsDashboard.tsx', import.meta.url), 'utf8');
const shell = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

// The portal shell is now the navy/cyan/mint sidebar layout; the legacy session
// dashboard still stacks responsively behind VITE_ENABLE_AGENT_DASHBOARD.
assert.match(shell, /className="sts-layout"/);
assert.match(app, /className="session-dashboard"/);
assert.match(app, /className="session-sidebar"/);
assert.match(css, /@media\s*\(max-width:\s*720px\)/);
assert.match(css, /\.session-dashboard\s*{[^}]*grid-template-columns:\s*minmax\(280px,\s*1fr\)\s+minmax\(360px,\s*2fr\)/s);
assert.match(css, /@media\s*\(max-width:\s*720px\)\s*{[\s\S]*\.session-dashboard\s*{[^}]*grid-template-columns:\s*1fr/s);
// On mobile the sidebar collapses to a top bar and the main column tightens up.
assert.match(css, /@media\s*\(max-width:\s*720px\)\s*{[\s\S]*\.sts-layout\s*{[^}]*flex-direction:\s*column/s);
assert.match(css, /@media\s*\(max-width:\s*720px\)\s*{[\s\S]*\.sts-main\s*{[^}]*padding:\s*20px/s);

console.log('mobile stacked layout verification passed');
