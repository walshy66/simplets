import type { CurrentStateComment, CurrentStateLane, CurrentStateMap, CurrentStateNode, CurrentStatePhase, CurrentStatePosition } from './api';

export type CurrentStateLaneType = NonNullable<CurrentStateLane['lane_type']>;
export type CurrentStateNodeType = 'start' | 'end' | 'decision' | 'process' | 'document';

export const CURRENT_STATE_LANE_TYPES: { value: CurrentStateLaneType; label: string }[] = [
  { value: 'role-team', label: 'Role/team' },
  { value: 'system-application', label: 'System/application' },
  { value: 'external-client', label: 'External client' },
  { value: 'other', label: 'Other' },
];

export const CURRENT_STATE_NODE_TYPES: { value: CurrentStateNodeType; label: string }[] = [
  { value: 'start', label: 'Start' },
  { value: 'end', label: 'End' },
  { value: 'decision', label: 'Decision' },
  { value: 'process', label: 'Process' },
  { value: 'document', label: 'Document' },
];

export type CurrentStateCanvasCell = {
  laneId: string;
  phaseId: string;
  nodes: CurrentStateNode[];
};

export type CurrentStateCanvas = {
  lanes: CurrentStateLane[];
  phases: CurrentStatePhase[];
  cells: CurrentStateCanvasCell[];
  nodePlacement: Record<string, { gridColumn: number; gridRow: number }>;
};

export const DEFAULT_CURRENT_STATE_NODE_POSITION: CurrentStatePosition = { x: 160, y: 120 };

export function currentStateNodePosition(node: CurrentStateNode, index = 0): CurrentStatePosition {
  return node.position ?? { x: DEFAULT_CURRENT_STATE_NODE_POSITION.x + index * 220, y: DEFAULT_CURRENT_STATE_NODE_POSITION.y };
}

export type CurrentStateMapRoute =
  | { kind: 'list' }
  | { kind: 'detail'; mapId: string };

export function parseCurrentStateMapRoute(pathname: string): CurrentStateMapRoute | null {
  const normalized = pathname.replace(/\/+$/, '') || '/';
  if (normalized === '/process-maps') {
    return { kind: 'list' };
  }
  const match = normalized.match(/^\/process-maps\/([^/]+)$/);
  if (!match) {
    return null;
  }
  return { kind: 'detail', mapId: decodeURIComponent(match[1]) };
}

export function currentStateMapPath(route: CurrentStateMapRoute): string {
  return route.kind === 'list' ? '/process-maps' : `/process-maps/${encodeURIComponent(route.mapId)}`;
}

export function currentStateMapSummary(map: CurrentStateMap): string {
  const phaseCount = map.phases.length;
  const nodeCount = map.nodes.length;
  return `${phaseCount} ${phaseCount === 1 ? 'phase' : 'phases'} · ${nodeCount} ${nodeCount === 1 ? 'step' : 'steps'} · ${map.status}`;
}

export function currentStateMapVersionLabel(map: CurrentStateMap): string {
  return map.version_ref ? `${map.version_ref} (${map.status})` : `Unsaved version (${map.status})`;
}

function assertEditable(map: CurrentStateMap): void {
  if (map.status !== 'draft') {
    throw new Error('only draft current-state map versions can be edited');
  }
}

export function defaultCurrentStateMapTitle(maps: CurrentStateMap[]): string {
  return maps.length === 0 ? 'Current-state process map' : `Current-state process map ${maps.length + 1}`;
}

export type CurrentStateMapExportMetadata = {
  title: string;
  workspaceClient: string;
  versionStatusDate: string;
};

function formatExportDate(value: string | null | undefined): string {
  if (!value) return 'date unavailable';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'date unavailable';
  return new Intl.DateTimeFormat('en-AU', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(date);
}

function slugifyExportPart(value: string): string {
  const slug = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || 'current-state-process-map';
}

export function buildCurrentStateMapExportMetadata(map: CurrentStateMap, workspaceClient: string): CurrentStateMapExportMetadata {
  const version = map.version_ref?.trim() || 'unsaved version';
  return {
    title: map.title,
    workspaceClient: workspaceClient.trim() || map.workspace_id,
    versionStatusDate: `${version} · ${map.status} · ${formatExportDate(map.updated_at ?? map.created_at)}`,
  };
}

export function currentStateMapExportFilename(map: CurrentStateMap, format: 'png' | 'pdf'): string {
  const version = map.version_ref?.trim() || map.status;
  return `${slugifyExportPart(map.title)}-${slugifyExportPart(version)}.${format}`;
}

export function buildCurrentStateCanvas(map: CurrentStateMap): CurrentStateCanvas {
  const cells = map.lanes.flatMap((lane) =>
    map.phases.map((phase) => ({
      laneId: lane.id,
      phaseId: phase.id,
      nodes: map.nodes.filter((node) => node.lane_id === lane.id && node.phase_id === phase.id),
    })),
  );
  const nodePlacement = Object.fromEntries(
    map.nodes.map((node) => [
      node.id,
      {
        gridColumn: Math.max(1, map.phases.findIndex((phase) => phase.id === node.phase_id) + 1),
        gridRow: Math.max(1, map.lanes.findIndex((lane) => lane.id === node.lane_id) + 1),
      },
    ]),
  );
  return { lanes: map.lanes, phases: map.phases, cells, nodePlacement };
}

export function renameCurrentStateLane(map: CurrentStateMap, laneId: string, title: string): CurrentStateMap {
  assertEditable(map);
  const trimmedTitle = title.trim();
  if (!trimmedTitle) {
    throw new Error('lane title is required');
  }
  return {
    ...map,
    lanes: map.lanes.map((lane) => (lane.id === laneId ? { ...lane, title: trimmedTitle } : lane)),
  };
}

export function renameCurrentStatePhase(map: CurrentStateMap, phaseId: string, title: string): CurrentStateMap {
  assertEditable(map);
  const trimmedTitle = title.trim();
  if (!trimmedTitle) {
    throw new Error('phase title is required');
  }
  return {
    ...map,
    phases: map.phases.map((phase) => (phase.id === phaseId ? { ...phase, title: trimmedTitle } : phase)),
  };
}

export function changeCurrentStateLaneType(
  map: CurrentStateMap,
  laneId: string,
  laneType: CurrentStateLaneType,
): CurrentStateMap {
  assertEditable(map);
  return {
    ...map,
    lanes: map.lanes.map((lane) => (lane.id === laneId ? { ...lane, lane_type: laneType } : lane)),
  };
}

function requireValidCell(map: CurrentStateMap, laneId: string, phaseId: string): void {
  if (!map.lanes.some((lane) => lane.id === laneId)) {
    throw new Error('node move requires a valid lane');
  }
  if (!map.phases.some((phase) => phase.id === phaseId)) {
    throw new Error('node move requires a valid phase');
  }
}

function nextLocalId(prefix: string, existingIds: string[]): string {
  let index = existingIds.length + 1;
  let id = `${prefix}-${index}`;
  while (existingIds.includes(id)) {
    index += 1;
    id = `${prefix}-${index}`;
  }
  return id;
}

export function addCurrentStateNode(
  map: CurrentStateMap,
  nodeType: CurrentStateNodeType,
  laneId: string | null,
  phaseId: string | null,
  title: string,
  position?: CurrentStatePosition,
): CurrentStateMap {
  assertEditable(map);
  if (laneId !== null && phaseId !== null) requireValidCell(map, laneId, phaseId);
  const trimmedTitle = title.trim() || CURRENT_STATE_NODE_TYPES.find((candidate) => candidate.value === nodeType)?.label || 'Process';
  return {
    ...map,
    nodes: [
      ...map.nodes,
      {
        id: nextLocalId('node', map.nodes.map((node) => node.id)),
        lane_id: laneId,
        phase_id: phaseId,
        title: trimmedTitle,
        node_type: nodeType,
        position: position ?? { x: 160 + map.nodes.length * 220, y: 140 },
      },
    ],
  };
}

export function moveCurrentStateNode(map: CurrentStateMap, nodeId: string, position: CurrentStatePosition): CurrentStateMap {
  assertEditable(map);
  return {
    ...map,
    nodes: map.nodes.map((node) => (node.id === nodeId ? { ...node, position } : node)),
  };
}

export function addCurrentStateLane(map: CurrentStateMap, title = 'Visual lane'): CurrentStateMap {
  assertEditable(map);
  return {
    ...map,
    lanes: [
      ...map.lanes,
      {
        id: nextLocalId('lane', map.lanes.map((lane) => lane.id)),
        title,
        lane_type: 'other',
      },
    ],
  };
}

export function renameCurrentStateNode(map: CurrentStateMap, nodeId: string, title: string): CurrentStateMap {
  assertEditable(map);
  const trimmedTitle = title.trim();
  if (!trimmedTitle) {
    throw new Error('node title is required');
  }
  return {
    ...map,
    nodes: map.nodes.map((node) => (node.id === nodeId ? { ...node, title: trimmedTitle } : node)),
  };
}

export function moveCurrentStateNodeToCell(
  map: CurrentStateMap,
  nodeId: string,
  laneId: string,
  phaseId: string,
): CurrentStateMap {
  assertEditable(map);
  requireValidCell(map, laneId, phaseId);
  return {
    ...map,
    nodes: map.nodes.map((node) => (node.id === nodeId ? { ...node, lane_id: laneId, phase_id: phaseId } : node)),
  };
}

export function addCurrentStateConnector(
  map: CurrentStateMap,
  sourceNodeId: string,
  targetNodeId: string,
  label = '',
): CurrentStateMap {
  assertEditable(map);
  const nodeIds = new Set(map.nodes.map((node) => node.id));
  if (!nodeIds.has(sourceNodeId) || !nodeIds.has(targetNodeId)) {
    throw new Error('connector requires valid source and target nodes');
  }
  return {
    ...map,
    connectors: [
      ...map.connectors,
      {
        id: nextLocalId('connector', map.connectors.map((connector) => connector.id)),
        source_node_id: sourceNodeId,
        target_node_id: targetNodeId,
        label: label.trim(),
      },
    ],
  };
}

export function renameCurrentStateConnector(map: CurrentStateMap, connectorId: string, label: string): CurrentStateMap {
  assertEditable(map);
  return {
    ...map,
    connectors: map.connectors.map((connector) => (connector.id === connectorId ? { ...connector, label: label.trim() } : connector)),
  };
}

export function addCurrentStateComment(
  map: CurrentStateMap,
  nodeId: string | null,
  body: string,
  author: string,
  createdAt: string,
): CurrentStateMap {
  if (nodeId !== null && !map.nodes.some((node) => node.id === nodeId)) {
    throw new Error('comment requires a valid node');
  }
  const trimmedBody = body.trim();
  if (!trimmedBody) {
    throw new Error('comment body is required');
  }
  const comment: CurrentStateComment = {
    id: nextLocalId('comment', map.comments.map((candidate) => candidate.id)),
    body: trimmedBody,
    node_id: nodeId,
    version_ref: map.version_ref,
    author,
    created_at: createdAt,
    resolved: false,
  };
  return { ...map, comments: [...map.comments, comment] };
}
