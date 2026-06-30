import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type OnConnect,
  type OnNodeDrag,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  acceptCurrentStateMap,
  addCurrentStateMapComment,
  createCurrentStateMap,
  duplicateCurrentStateMap,
  getCurrentStateMap,
  listCurrentStateMapVersions,
  listCurrentStateMaps,
  listCurrentStateImports,
  dismissCurrentStateImport,
  retryCurrentStateImport,
  updateCurrentStateMap,
  uploadCurrentStateImport,
  type CurrentStateImportJob,
  type CurrentStateMap,
} from '../api';
import {
  CURRENT_STATE_LANE_TYPES,
  CURRENT_STATE_NODE_TYPES,
  addCurrentStateConnector,
  addCurrentStateLane,
  addCurrentStateNode,
  buildCurrentStateMapExportMetadata,
  changeCurrentStateLaneType,
  currentStateMapExportFilename,
  currentStateMapPath,
  currentStateMapSummary,
  currentStateMapVersionLabel,
  currentStateNodePosition,
  defaultCurrentStateMapTitle,
  moveCurrentStateNode,
  parseCurrentStateMapRoute,
  renameCurrentStateConnector,
  renameCurrentStateLane,
  renameCurrentStateNode,
  type CurrentStateNodeType,
} from '../currentStateMapModel';

type Props = {
  onNavigate: (path: string) => void;
};

const PROCESS_MAP_IMPORT_ACCEPT = 'application/pdf,image/png,image/jpeg,image/svg+xml,.drawio,.xml,.vsdx,.bpmn,.mmd,.mermaid,.puml,.plantuml,.dot,.graphml';
const PROCESS_MAP_IMPORT_MAX_BYTES = 25 * 1024 * 1024;

type ProcessFlowNodeData = {
  title: string;
  nodeType: string;
  locked: boolean;
  onRename: (nodeId: string, title: string) => void;
  onComment: (nodeId: string) => void;
};

type VisualLaneNodeData = {
  title: string;
  laneType: typeof CURRENT_STATE_LANE_TYPES[number]['value'];
  locked: boolean;
  onRename: (laneId: string, title: string) => void;
  onTypeChange: (laneId: string, laneType: typeof CURRENT_STATE_LANE_TYPES[number]['value']) => void;
};

function ProcessFlowNode({ id, data }: NodeProps<Node<ProcessFlowNodeData>>) {
  const label = data.nodeType === 'process' ? 'Process' : data.nodeType.charAt(0).toUpperCase() + data.nodeType.slice(1);
  return (
    <article className={`process-map-flow-node process-map-node process-map-node-${data.nodeType}`}>
      <Handle type="target" position={Position.Left} isConnectable={!data.locked} />
      <div className="process-map-node-content">
        <input
          aria-label={`${data.nodeType} shape label`}
          value={data.title}
          disabled={data.locked}
          onChange={(event) => data.onRename(id, event.target.value)}
        />
        <span>{label}</span>
        <button type="button" onClick={() => data.onComment(id)}>Comment</button>
      </div>
      <Handle type="source" position={Position.Right} isConnectable={!data.locked} />
    </article>
  );
}

function VisualLaneNode({ id, data }: NodeProps<Node<VisualLaneNodeData>>) {
  const laneId = id.replace(/^lane-/, '');
  return (
    <label className="process-map-visual-lane-node nodrag">
      <span className="sr-only">Visual lane title</span>
      <input
        value={data.title}
        disabled={data.locked}
        onChange={(event) => data.onRename(laneId, event.target.value)}
      />
      <select
        aria-label={`${data.title} lane type`}
        value={data.laneType}
        disabled={data.locked}
        onChange={(event) => data.onTypeChange(laneId, event.target.value as typeof CURRENT_STATE_LANE_TYPES[number]['value'])}
      >
        {CURRENT_STATE_LANE_TYPES.map((laneType) => <option key={laneType.value} value={laneType.value}>{laneType.label}</option>)}
      </select>
    </label>
  );
}

const PROCESS_FLOW_NODE_TYPES = { processShape: ProcessFlowNode, visualLane: VisualLaneNode };

export default function CurrentStateMapsPage({ onNavigate }: Props) {
  const [maps, setMaps] = useState<CurrentStateMap[]>([]);
  const [selectedMap, setSelectedMap] = useState<CurrentStateMap | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [versions, setVersions] = useState<CurrentStateMap[]>([]);
  const [importJobs, setImportJobs] = useState<CurrentStateImportJob[]>([]);
  const [importStatus, setImportStatus] = useState<'idle' | 'uploading'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [currentPath, setCurrentPath] = useState(() => window.location.pathname);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [pendingPath, setPendingPath] = useState<string | null>(null);
  const [saveTitle, setSaveTitle] = useState('');
  const selectedRoute = parseCurrentStateMapRoute(currentPath);
  const exportFrameRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    document.body.classList.toggle('process-map-open', selectedMap !== null);
    return () => document.body.classList.remove('process-map-open');
  }, [selectedMap]);

  useEffect(() => {
    const syncPath = () => setCurrentPath(window.location.pathname);
    window.addEventListener('popstate', syncPath);
    return () => window.removeEventListener('popstate', syncPath);
  }, []);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [hasUnsavedChanges]);

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    setError(null);
    listCurrentStateMaps()
      .then(async (loadedMaps) => {
        if (cancelled) return;
        setMaps(loadedMaps);
        setImportJobs(await listCurrentStateImports());
        if (selectedRoute?.kind === 'detail') {
          const loadedMap = await getCurrentStateMap(selectedRoute.mapId);
          setSelectedMap(loadedMap);
          setSaveTitle(loadedMap.title);
          setHasUnsavedChanges(false);
          setVersions(await listCurrentStateMapVersions(selectedRoute.mapId));
        } else {
          setSelectedMap(null);
          setSaveTitle('');
          setHasUnsavedChanges(false);
          setVersions([]);
        }
        setStatus('ready');
      })
      .catch(() => {
        if (cancelled) return;
        setStatus('error');
        setError('Process maps are only available to workspace staff.');
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRoute?.kind, selectedRoute?.kind === 'detail' ? selectedRoute.mapId : '']);

  async function handleCreate() {
    setStatus('loading');
    setError(null);
    try {
      const created = await createCurrentStateMap({ title: defaultCurrentStateMapTitle(maps) });
      setMaps((currentMaps) => [...currentMaps, created]);
      setSelectedMap(created);
      setSaveTitle(created.title);
      setHasUnsavedChanges(false);
      navigateToMapPath(currentStateMapPath({ kind: 'detail', mapId: created.id }));
      setStatus('ready');
    } catch {
      setStatus('error');
      setError('Unable to create a process map for this workspace.');
    }
  }

  function navigateToMapPath(path: string) {
    onNavigate(path);
    setCurrentPath(path);
  }

  function requestNavigate(path: string) {
    const activeMap = selectedMap;
    if (hasUnsavedChanges && activeMap && activeMap.status === 'draft') {
      setSaveTitle(activeMap.title);
      setPendingPath(path);
      return;
    }
    navigateToMapPath(path);
  }

  function replaceSelectedMap(nextMap: CurrentStateMap, dirty = true) {
    setSelectedMap(nextMap);
    setSaveTitle(nextMap.title);
    setHasUnsavedChanges(dirty);
    setMaps((currentMaps) => (currentMaps.some((map) => map.id === nextMap.id) ? currentMaps.map((map) => (map.id === nextMap.id ? nextMap : map)) : [...currentMaps, nextMap]));
  }

  async function saveMap(map: CurrentStateMap): Promise<CurrentStateMap> {
    const saved = await updateCurrentStateMap(map.id, {
      title: map.title,
      version_ref: map.version_ref,
      status: map.status,
      source_version_id: map.source_version_id,
      lanes: map.lanes,
      phases: map.phases,
      nodes: map.nodes,
      connectors: map.connectors,
      comments: map.comments,
    });
    replaceSelectedMap(saved, false);
    if (saved.id !== map.id) navigateToMapPath(currentStateMapPath({ kind: 'detail', mapId: saved.id }));
    setVersions(await listCurrentStateMapVersions(saved.id));
    return saved;
  }

  async function handleSave() {
    if (!selectedMap || selectedMap.status !== 'draft') return;
    setError(null);
    try {
      await saveMap(selectedMap);
    } catch {
      setError('Unable to save this process map version. Only drafts can be edited.');
    }
  }

  async function handleDuplicateLockedVersion() {
    if (!selectedMap) return;
    setError(null);
    try {
      const duplicated = await duplicateCurrentStateMap(selectedMap.id);
      setMaps((currentMaps) => [...currentMaps, duplicated]);
      setSelectedMap(duplicated);
      setSaveTitle(duplicated.title);
      setHasUnsavedChanges(false);
      setVersions(await listCurrentStateMapVersions(duplicated.id));
      navigateToMapPath(currentStateMapPath({ kind: 'detail', mapId: duplicated.id }));
    } catch {
      setError('Unable to duplicate this process map version.');
    }
  }

  function handleAddNode(nodeType: CurrentStateNodeType) {
    if (!selectedMap) return;
    replaceSelectedMap(addCurrentStateNode(selectedMap, nodeType, null, null, CURRENT_STATE_NODE_TYPES.find((candidate) => candidate.value === nodeType)?.label ?? 'Process'));
  }

  function handleAddLane() {
    if (!selectedMap) return;
    replaceSelectedMap(addCurrentStateLane(selectedMap));
  }

  const handleConnect: OnConnect = (connection: Connection) => {
    if (!selectedMap || !connection.source || !connection.target) return;
    replaceSelectedMap(addCurrentStateConnector(selectedMap, connection.source, connection.target, ''));
  };

  const handleNodeDragStop: OnNodeDrag = (_event, node) => {
    if (!selectedMap || selectedMap.status !== 'draft') return;
    replaceSelectedMap(moveCurrentStateNode(selectedMap, node.id, node.position));
  };

  async function handleAccept() {
    if (!selectedMap) return;
    setError(null);
    try {
      const approved = await acceptCurrentStateMap(selectedMap.id);
      replaceSelectedMap(approved, false);
      setMaps(await listCurrentStateMaps());
      setVersions(await listCurrentStateMapVersions(approved.id));
    } catch {
      setError('Unable to approve this process map version.');
    }
  }

  async function handleAddComment(nodeId: string | null) {
    if (!selectedMap) return;
    const body = window.prompt(nodeId ? 'Add a comment for this shape' : 'Add a workflow comment');
    if (!body?.trim()) return;
    setError(null);
    try {
      replaceSelectedMap(await addCurrentStateMapComment(selectedMap.id, { node_id: nodeId, body: body.trim(), resolved: false }), false);
    } catch {
      setError('Unable to add this process map comment.');
    }
  }

  async function handleUploadImport(file: File | null) {
    if (!file) return;
    setError(null);
    if (file.size > PROCESS_MAP_IMPORT_MAX_BYTES) {
      setError('Process map imports must be 25 MB or smaller.');
      return;
    }
    setImportStatus('uploading');
    try {
      const uploaded = await uploadCurrentStateImport(file);
      setImportJobs((jobs) => [uploaded, ...jobs]);
      if (uploaded.result_map_id) {
        const refreshedMaps = await listCurrentStateMaps();
        setMaps(refreshedMaps);
        const importedMap = refreshedMaps.find((map) => map.id === uploaded.result_map_id);
        if (importedMap) {
          setSelectedMap(importedMap);
          setSaveTitle(importedMap.title);
          setHasUnsavedChanges(false);
        }
      }
    } catch {
      setError('Unable to upload this process map.');
    } finally {
      setImportStatus('idle');
    }
  }

  async function handleRetryImport(jobId: string) {
    setError(null);
    try {
      const retried = await retryCurrentStateImport(jobId);
      setImportJobs((jobs) => jobs.map((job) => (job.id === retried.id ? retried : job)));
    } catch {
      setError('Unable to retry this conversion job.');
    }
  }

  async function handleDismissImport(jobId: string) {
    setError(null);
    try {
      await dismissCurrentStateImport(jobId);
      setImportJobs((jobs) => jobs.filter((job) => job.id !== jobId));
    } catch {
      setError('Unable to dismiss this failed import.');
    }
  }

  async function handleExportPng() {
    if (!selectedMap || !exportFrameRef.current) return;
    setError(null);
    try {
      const source = exportFrameRef.current;
      const width = Math.max(source.scrollWidth, source.clientWidth, 800);
      const height = Math.max(source.scrollHeight, source.clientHeight, 600);
      const cloned = source.cloneNode(true) as HTMLElement;
      cloned.querySelectorAll('input, select').forEach((control) => {
        const replacement = document.createElement('span');
        replacement.textContent = control instanceof HTMLSelectElement ? control.selectedOptions[0]?.textContent ?? control.value : (control as HTMLInputElement).value;
        replacement.className = control.className;
        control.replaceWith(replacement);
      });
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><foreignObject width="100%" height="100%"><div xmlns="http://www.w3.org/1999/xhtml">${cloned.outerHTML}</div></foreignObject></svg>`;
      const imageUrl = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }));
      const image = new Image();
      await new Promise<void>((resolve, reject) => {
        image.onload = () => resolve();
        image.onerror = () => reject(new Error('Unable to render export image'));
        image.src = imageUrl;
      });
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext('2d');
      if (!context) throw new Error('Unable to create export canvas');
      context.fillStyle = '#ffffff';
      context.fillRect(0, 0, width, height);
      context.drawImage(image, 0, 0);
      URL.revokeObjectURL(imageUrl);
      const link = document.createElement('a');
      link.download = currentStateMapExportFilename(selectedMap, 'png');
      link.href = canvas.toDataURL('image/png');
      link.click();
    } catch {
      setError('Unable to export this process map as PNG.');
    }
  }

  async function handleSaveBeforeNavigate() {
    if (!selectedMap || !pendingPath) return;
    const title = saveTitle.trim();
    if (!title) {
      setError('Workflow name is required before saving.');
      return;
    }
    setError(null);
    try {
      await saveMap({ ...selectedMap, title });
      const nextPath = pendingPath;
      setPendingPath(null);
      navigateToMapPath(nextPath);
    } catch {
      setError('Unable to save this process map before leaving.');
    }
  }

  function handleDiscardBeforeNavigate() {
    if (!pendingPath) return;
    const nextPath = pendingPath;
    setPendingPath(null);
    setHasUnsavedChanges(false);
    navigateToMapPath(nextPath);
  }

  function handleExportPdf() {
    if (!selectedMap || !exportFrameRef.current) return;
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      setError('Unable to open the PDF export window.');
      return;
    }
    const styles = Array.from(document.querySelectorAll('style, link[rel="stylesheet"]')).map((element) => element.outerHTML).join('\n');
    printWindow.document.write(`<!doctype html><html><head><title>${currentStateMapExportFilename(selectedMap, 'pdf')}</title>${styles}</head><body>${exportFrameRef.current.outerHTML}</body></html>`);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  }

  const flowNodes = useMemo<Node[]>(() => {
    if (!selectedMap) return [];
    const laneNodes: Node<VisualLaneNodeData>[] = selectedMap.lanes.map((lane, index) => ({
      id: `lane-${lane.id}`,
      type: 'visualLane',
      position: { x: 20, y: 92 + index * 190 },
      data: {
        title: lane.title,
        laneType: lane.lane_type ?? 'other',
        locked: selectedMap.status !== 'draft',
        onRename: (laneId, title) => replaceSelectedMap(renameCurrentStateLane(selectedMap, laneId, title)),
        onTypeChange: (laneId, laneType) => replaceSelectedMap(changeCurrentStateLaneType(selectedMap, laneId, laneType)),
      },
      draggable: false,
      selectable: false,
      connectable: false,
      zIndex: -1,
    }));
    const processNodes: Node<ProcessFlowNodeData>[] = selectedMap.nodes.map((node, index) => ({
      id: node.id,
      type: 'processShape',
      position: currentStateNodePosition(node, index),
      data: {
        title: node.title,
        nodeType: node.node_type,
        locked: selectedMap.status !== 'draft',
        onRename: (nodeId, title) => replaceSelectedMap(renameCurrentStateNode(selectedMap, nodeId, title)),
        onComment: (nodeId) => handleAddComment(nodeId),
      },
    }));
    return [...laneNodes, ...processNodes];
  }, [selectedMap]);
  const flowEdges = useMemo<Edge[]>(() => {
    if (!selectedMap) return [];
    return selectedMap.connectors.map((connector) => ({
      id: connector.id,
      source: connector.source_node_id,
      target: connector.target_node_id,
      label: connector.label ?? undefined,
      markerEnd: { type: MarkerType.ArrowClosed },
      type: 'smoothstep',
    }));
  }, [selectedMap]);
  const exportMetadata = selectedMap ? buildCurrentStateMapExportMetadata(selectedMap, selectedMap.workspace_id) : null;

  return (
    <section className="panel process-map-shell" aria-labelledby="process-maps-heading">
      <div className="panel-heading-row">
        <div>
          <p className="eyebrow">Current state</p>
          <h2 id="process-maps-heading">Process maps</h2>
          <p className="muted">Create and open workspace-scoped current-state process maps.</p>
        </div>
        <button type="button" onClick={handleCreate} disabled={status === 'loading'}>
          New map
        </button>
      </div>
      {error ? <p role="alert" className="error-text">{error}</p> : null}
      {status === 'loading' ? <p>Loading process maps…</p> : null}
      <section className="process-map-imports" aria-label="Process map import conversion jobs">
        <div className="panel-heading-row">
          <div>
            <h3>Import process map</h3>
            <p className="muted">Upload a process map to create an AI-assisted Current State draft. You can edit the result before approving it. Source files are temporary and deleted after conversion.</p>
          </div>
          <label className="button-like">
            {importStatus === 'uploading' ? 'Uploading…' : 'Upload process map'}
            <input
              type="file"
              accept={PROCESS_MAP_IMPORT_ACCEPT}
              disabled={importStatus === 'uploading'}
              onChange={(event) => handleUploadImport(event.target.files?.[0] ?? null)}
            />
          </label>
        </div>
        {importJobs.length === 0 ? <p className="muted">No conversion jobs yet.</p> : null}
        {importJobs.map((job) => (
          <article key={job.id} className={`import-job import-job-${job.status}`}>
            <strong>{job.filename_display ?? job.filename_redacted}</strong>
            <span>{job.file_type} · uploaded by {job.uploader}</span>
            <span>Status: {job.status}</span>
            {job.result_map_id ? <span>Draft map created — review and clean up before use.</span> : null}
            {job.error_message ? <span role="alert">{job.error_message}</span> : null}
            {job.status === 'failed' ? (
              <span className="import-job-actions">
                <button type="button" onClick={() => handleRetryImport(job.id)}>Retry</button>
                <button type="button" onClick={() => handleDismissImport(job.id)}>Dismiss</button>
              </span>
            ) : null}
          </article>
        ))}
      </section>
      {status !== 'loading' && maps.length === 0 ? <p>No process maps yet. Start with a default Process phase.</p> : null}
      {maps.length > 0 ? (
        <div className="process-map-grid">
          <ul className="process-map-list" aria-label="Process maps">
            {maps.map((map) => (
              <li key={map.id}>
                <button type="button" onClick={() => requestNavigate(currentStateMapPath({ kind: 'detail', mapId: map.id }))}>
                  <strong>{map.title}</strong>
                  <span>{currentStateMapSummary(map)}</span>
                </button>
              </li>
            ))}
          </ul>
          {selectedMap ? createPortal(
            <article className="process-map-detail process-map-detail-fullscreen" aria-label="Process map detail">
              <>
                <div className="process-map-export-frame" ref={exportFrameRef} aria-label="Process map export preview">
                  <div className="process-map-flow-canvas" aria-label={`${selectedMap.title} freeform process canvas`}>
                    <div className="process-map-floating-panel process-map-floating-header">
                      <button className="process-map-home-button" type="button" onClick={() => requestNavigate(currentStateMapPath({ kind: 'list' }))} aria-label="Back to process maps">⌂</button>
                      <div className="process-map-floating-title">
                        <p className="eyebrow">Current-state process map</p>
                        <strong>{selectedMap.title}</strong>
                        <span>{currentStateMapSummary(selectedMap)} · {currentStateMapVersionLabel(selectedMap)}</span>
                      </div>
                      <div className="process-map-floating-actions" aria-label="Process map actions">
                        <button type="button" onClick={handleSave} disabled={selectedMap.status !== 'draft'}>Save</button>
                        <button type="button" onClick={handleAccept} disabled={selectedMap.status !== 'draft'}>Approve</button>
                        <button type="button" onClick={handleDuplicateLockedVersion}>Duplicate</button>
                        <button type="button" onClick={handleExportPng}>PNG</button>
                        <button type="button" onClick={handleExportPdf}>PDF</button>
                        {versions.length > 0 ? (
                          <select
                            aria-label="Version history"
                            value={selectedMap.id}
                            onChange={async (event) => {
                              const loaded = await getCurrentStateMap(event.target.value);
                              setSelectedMap(loaded);
                              setSaveTitle(loaded.title);
                              setHasUnsavedChanges(false);
                              navigateToMapPath(currentStateMapPath({ kind: 'detail', mapId: loaded.id }));
                            }}
                          >
                            {versions.map((version) => <option key={version.id} value={version.id}>{currentStateMapVersionLabel(version)}</option>)}
                          </select>
                        ) : null}
                      </div>
                    </div>
                    <div className="process-map-floating-panel process-map-floating-palette" aria-label="Process map shape palette">
                      <strong>Shapes</strong>
                      {CURRENT_STATE_NODE_TYPES.map((nodeType) => (
                        <button key={nodeType.value} type="button" disabled={selectedMap.status !== 'draft'} onClick={() => handleAddNode(nodeType.value)}>
                          {nodeType.label}
                        </button>
                      ))}
                      <button type="button" disabled={selectedMap.status !== 'draft'} onClick={handleAddLane}>Add visual lane</button>
                    </div>
                    <div className="process-map-floating-panel process-map-floating-comments" aria-label="Process map comments">
                      <div className="panel-heading-row">
                        <h4>Comments</h4>
                        <button type="button" onClick={() => handleAddComment(null)}>Add</button>
                      </div>
                      {selectedMap.comments.length === 0 ? <p className="muted">No comments yet.</p> : null}
                      {selectedMap.comments.map((comment) => {
                        const node = selectedMap.nodes.find((candidate) => candidate.id === comment.node_id);
                        return (
                          <article key={comment.id} className="process-map-comment">
                            <strong>{node?.title ?? 'Workflow'}</strong>
                            <p>{comment.body}</p>
                            <small>{comment.author ?? 'Unknown author'} · {comment.resolved ? 'Resolved' : 'Open'}</small>
                          </article>
                        );
                      })}
                    </div>
                    {selectedMap.connectors.length > 0 ? (
                      <div className="process-map-floating-panel process-map-floating-connectors" aria-label="Process map connectors">
                        <h4>Connector labels</h4>
                        {selectedMap.connectors.map((connector) => {
                          const source = selectedMap.nodes.find((node) => node.id === connector.source_node_id);
                          const target = selectedMap.nodes.find((node) => node.id === connector.target_node_id);
                          return (
                            <label key={connector.id} className="process-map-connector-row">
                              <span>{source?.title ?? 'Unknown'} → {target?.title ?? 'Unknown'}</span>
                              <input
                                aria-label={`Connector label from ${source?.title ?? 'unknown'} to ${target?.title ?? 'unknown'}`}
                                value={connector.label ?? ''}
                                placeholder="Label"
                                disabled={selectedMap.status !== 'draft'}
                                onChange={(event) => replaceSelectedMap(renameCurrentStateConnector(selectedMap, connector.id, event.target.value))}
                              />
                            </label>
                          );
                        })}
                      </div>
                    ) : null}
                    <ReactFlowProvider>
                      <ReactFlow
                        nodes={flowNodes}
                        edges={flowEdges}
                        nodeTypes={PROCESS_FLOW_NODE_TYPES}
                        onConnect={handleConnect}
                        onNodeDragStop={handleNodeDragStop}
                        nodesDraggable={selectedMap.status === 'draft'}
                        nodesConnectable={selectedMap.status === 'draft'}
                        fitView
                      >
                        <Background />
                        <MiniMap />
                        <Controls />
                      </ReactFlow>
                    </ReactFlowProvider>
                  </div>
                </div>
                <p className="sr-only">Use the shape palette to add steps, drag shapes anywhere, and drag from one handle to another to create visible arrows. Visual lanes are for human readability only.</p>
              </>
            </article>,
            document.body,
          ) : (
            <article className="process-map-detail" aria-label="Process map detail">
              <p>Select a process map to open its detail shell.</p>
            </article>
          )}
        </div>
      ) : null}
      {pendingPath && selectedMap ? createPortal(
        <div className="process-map-save-modal-backdrop" role="presentation">
          <section className="process-map-save-modal" role="dialog" aria-modal="true" aria-labelledby="save-map-title">
            <h3 id="save-map-title">Save this workflow before leaving?</h3>
            <p className="muted">Name and save the current process map, or discard unsaved canvas changes.</p>
            <label>
              Workflow name
              <input value={saveTitle} onChange={(event) => setSaveTitle(event.target.value)} autoFocus />
            </label>
            <div className="process-map-save-modal-actions">
              <button type="button" onClick={handleSaveBeforeNavigate}>Save and leave</button>
              <button type="button" onClick={handleDiscardBeforeNavigate}>Discard changes</button>
              <button type="button" onClick={() => setPendingPath(null)}>Stay here</button>
            </div>
          </section>
        </div>,
        document.body,
      ) : null}
    </section>
  );
}
