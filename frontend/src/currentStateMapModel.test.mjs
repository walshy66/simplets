import assert from 'node:assert/strict';

import {
  CURRENT_STATE_NODE_TYPES,
  addCurrentStateComment,
  addCurrentStateConnector,
  addCurrentStateLane,
  addCurrentStateNode,
  buildCurrentStateCanvas,
  currentStateMapPath,
  currentStateMapSummary,
  currentStateMapVersionLabel,
  defaultCurrentStateMapTitle,
  buildCurrentStateMapExportMetadata,
  currentStateMapExportFilename,
  moveCurrentStateNode,
  moveCurrentStateNodeToCell,
  parseCurrentStateMapRoute,
  renameCurrentStateConnector,
  renameCurrentStateLane,
  renameCurrentStateNode,
  renameCurrentStatePhase,
} from './currentStateMapModel.ts';

assert.deepEqual(parseCurrentStateMapRoute('/process-maps'), { kind: 'list' });
assert.deepEqual(parseCurrentStateMapRoute('/process-maps/'), { kind: 'list' });
assert.deepEqual(parseCurrentStateMapRoute('/process-maps/map%201'), { kind: 'detail', mapId: 'map 1' });
assert.equal(parseCurrentStateMapRoute('/review'), null);
assert.equal(currentStateMapPath({ kind: 'list' }), '/process-maps');
assert.equal(currentStateMapPath({ kind: 'detail', mapId: 'map 1' }), '/process-maps/map%201');

assert.equal(
  currentStateMapSummary({
    id: 'm1',
    workspace_id: 'ws-a',
    title: 'Onboarding',
    version_ref: null,
    status: 'draft',
    source_version_id: null,
    lanes: [],
    phases: [{ id: 'process', title: 'Process' }],
    nodes: [],
    connectors: [],
    comments: [],
    created_at: '2026-01-01T00:00:00+00:00',
    updated_at: '2026-01-01T00:00:00+00:00',
  }),
  '1 phase · 0 steps · draft',
);
assert.equal(defaultCurrentStateMapTitle([]), 'Current-state process map');
assert.equal(defaultCurrentStateMapTitle([{ id: 'm1' }]), 'Current-state process map 2');

const exportMap = {
  id: 'export-1',
  workspace_id: 'ws-a',
  title: 'Client onboarding',
  version_ref: 'accepted-v1',
  status: 'approved',
  source_version_id: null,
  lanes: [],
  phases: [],
  nodes: [],
  connectors: [],
  comments: [],
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-03T04:05:06+00:00',
};
assert.deepEqual(buildCurrentStateMapExportMetadata(exportMap, 'Client A'), {
  title: 'Client onboarding',
  workspaceClient: 'Client A',
  versionStatusDate: 'accepted-v1 · approved · 3 Jan 2026',
});
assert.equal(currentStateMapExportFilename(exportMap, 'png'), 'client-onboarding-accepted-v1.png');
assert.equal(currentStateMapExportFilename({ ...exportMap, version_ref: null, status: 'draft' }, 'pdf'), 'client-onboarding-draft.pdf');

const canvasMap = {
  id: 'm2',
  workspace_id: 'ws-a',
  title: 'Client onboarding',
  version_ref: null,
  status: 'draft',
  source_version_id: null,
  lanes: [
    { id: 'sales', title: 'Sales', lane_type: 'role-team' },
    { id: 'crm', title: 'CRM', lane_type: 'system-application' },
    { id: 'client', title: 'Client', lane_type: 'external-client' },
    { id: 'misc', title: 'Exceptions', lane_type: 'other' },
  ],
  phases: [
    { id: 'intake', title: 'Intake' },
    { id: 'review', title: 'Review' },
  ],
  nodes: [
    { id: 'n1', lane_id: 'sales', phase_id: 'intake', title: 'Receive request', node_type: 'task' },
    { id: 'n2', lane_id: 'crm', phase_id: 'review', title: 'Update record', node_type: 'system' },
  ],
  connectors: [],
  comments: [],
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-01T00:00:00+00:00',
};
const canvas = buildCurrentStateCanvas(canvasMap);
assert.equal(canvas.lanes[0].lane_type, 'role-team');
assert.equal(canvas.cells.find((cell) => cell.laneId === 'sales' && cell.phaseId === 'intake').nodes[0].id, 'n1');
assert.equal(canvas.cells.find((cell) => cell.laneId === 'crm' && cell.phaseId === 'review').nodes[0].id, 'n2');
assert.equal(canvas.cells.length, 8);
assert.equal(canvas.nodePlacement.n1.gridColumn, 1);
assert.equal(canvas.nodePlacement.n1.gridRow, 1);

assert.equal(renameCurrentStateLane(canvasMap, 'sales', 'Revenue').lanes[0].title, 'Revenue');
assert.equal(renameCurrentStatePhase(canvasMap, 'review', 'QA').phases[1].title, 'QA');
const moved = moveCurrentStateNodeToCell(canvasMap, 'n1', 'client', 'review');
assert.deepEqual(
  moved.nodes.find((node) => node.id === 'n1'),
  { id: 'n1', lane_id: 'client', phase_id: 'review', title: 'Receive request', node_type: 'task' },
);
assert.throws(() => moveCurrentStateNodeToCell(canvasMap, 'n1', 'missing', 'review'), /valid lane/);

assert.deepEqual(
  CURRENT_STATE_NODE_TYPES.map((nodeType) => nodeType.value),
  ['start', 'end', 'decision', 'process', 'document'],
);
const withDecision = addCurrentStateNode(canvasMap, 'decision', 'sales', 'intake', 'Check eligibility');
assert.equal(withDecision.nodes.at(-1).node_type, 'decision');
assert.equal(withDecision.nodes.at(-1).title, 'Check eligibility');
assert.equal(withDecision.nodes.at(-1).lane_id, 'sales');
assert.equal(withDecision.nodes.at(-1).phase_id, 'intake');
assert.deepEqual(withDecision.nodes.at(-1).position, { x: 600, y: 140 });
const freeform = addCurrentStateNode(canvasMap, 'process', null, null, 'Freeform', { x: 44, y: 55 });
assert.equal(freeform.nodes.at(-1).lane_id, null);
assert.equal(freeform.nodes.at(-1).phase_id, null);
assert.deepEqual(freeform.nodes.at(-1).position, { x: 44, y: 55 });
assert.deepEqual(moveCurrentStateNode(freeform, freeform.nodes.at(-1).id, { x: 99, y: 100 }).nodes.at(-1).position, { x: 99, y: 100 });
assert.equal(addCurrentStateLane(canvasMap, 'Support').lanes.at(-1).title, 'Support');
assert.throws(() => addCurrentStateNode(canvasMap, 'process', 'missing', 'intake', 'Step'), /valid lane/);
assert.equal(renameCurrentStateNode(withDecision, withDecision.nodes.at(-1).id, 'Approved?').nodes.at(-1).title, 'Approved?');

const connected = addCurrentStateConnector(
  withDecision,
  'n1',
  'n2',
  'Yes',
);
assert.equal(connected.connectors.at(-1).source_node_id, 'n1');
assert.equal(connected.connectors.at(-1).target_node_id, 'n2');
assert.equal(connected.connectors.at(-1).label, 'Yes');
assert.equal(renameCurrentStateConnector(connected, connected.connectors.at(-1).id, 'No').connectors.at(-1).label, 'No');
assert.throws(() => addCurrentStateConnector(canvasMap, 'n1', 'missing', 'No'), /valid source and target/);

const commented = addCurrentStateComment(canvasMap, 'n1', 'Please confirm handoff', 'alice-reviewer', '2026-01-02T00:00:00+00:00');
assert.equal(commented.comments.at(-1).node_id, 'n1');
assert.equal(commented.comments.at(-1).body, 'Please confirm handoff');
assert.equal(commented.comments.at(-1).author, 'alice-reviewer');
assert.equal(commented.comments.at(-1).created_at, '2026-01-02T00:00:00+00:00');
assert.equal(commented.comments.at(-1).resolved, false);
assert.throws(() => addCurrentStateComment(canvasMap, 'missing', 'Bad', 'alice-reviewer', '2026-01-02T00:00:00+00:00'), /valid node/);

const approvedMap = { ...canvasMap, status: 'approved', version_ref: 'accepted-v1' };
assert.equal(currentStateMapVersionLabel(approvedMap), 'accepted-v1 (approved)');
assert.throws(() => renameCurrentStateNode(approvedMap, 'n1', 'Mutated'), /only draft current-state map versions can be edited/);
assert.throws(() => addCurrentStateNode(approvedMap, 'process', 'sales', 'intake', 'Step'), /only draft current-state map versions can be edited/);

console.log('currentStateMapModel tests passed');
