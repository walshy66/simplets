import hashlib
import html
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app import db
from app.auth import WorkspaceActor, require_any_staff
from app.db import get_connection
from app.schemas import CurrentStateComment, CurrentStateCommentCreate, CurrentStateImportJob, CurrentStateMap, CurrentStateMapCreate, CurrentStateMapUpdate
from app.tenancy import now_iso

router = APIRouter(prefix="/current-state-maps", tags=["current-state-maps"])
import_router = APIRouter(prefix="/current-state-imports", tags=["current-state-imports"])
# V1 keeps Current State permissions simple: every workspace staff member may
# create/edit/import/approve maps. Keep capability-specific names so future
# configurable role permissions can replace these seams without endpoint churn.
require_current_state_editor = require_any_staff
require_current_state_approver = require_any_staff
IMPORT_SOURCE_RETENTION_HOURS = 24
MAX_IMPORT_BYTES = 25 * 1024 * 1024
ACCEPTED_IMPORT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".svg", ".drawio", ".xml", ".vsdx", ".bpmn", ".mmd", ".mermaid", ".puml", ".plantuml", ".dot", ".graphml"}


def _json_dump(value: object) -> str:
    return json.dumps(value, separators=(",", ":"))


def _row_to_map(row: sqlite3.Row) -> CurrentStateMap:
    values = dict(row)
    for field in ("lanes", "phases", "nodes", "connectors", "comments"):
        values[field] = json.loads(values[field])
    return CurrentStateMap(**values)


def _row_to_import_job(row: sqlite3.Row) -> CurrentStateImportJob:
    values = dict(row)
    values.pop("temporary_storage_path", None)
    values.pop("source_deleted_at", None)
    values.pop("source_retention_expires_at", None)
    return CurrentStateImportJob(**values)


def _redacted_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return f"[redacted]{suffix}" if suffix else "[redacted]"


def _display_filename(filename: str) -> str:
    name = Path(filename).name or "import"
    cleaned = re.sub(r"[^A-Za-z0-9._() \-&]+", " ", name)
    return " ".join(cleaned.split())[:120] or _redacted_filename(filename)


def _get_workspace_import_job(job_id: str, workspace_id: str, conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM current_state_import_jobs WHERE id = ? AND workspace_id = ?",
        (job_id, workspace_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="current-state import job not found")
    return row


def _delete_import_source(row: sqlite3.Row, conn: sqlite3.Connection, timestamp: str) -> bool:
    storage_path = Path(row["temporary_storage_path"])
    deleted = False
    if storage_path.exists():
        storage_path.unlink()
        deleted = True
    conn.execute(
        "UPDATE current_state_import_jobs SET source_deleted_at = ?, updated_at = ? WHERE id = ?",
        (timestamp, timestamp, row["id"]),
    )
    return deleted


def cleanup_expired_import_sources(now: datetime | None = None, conn: sqlite3.Connection | None = None) -> int:
    """Delete expired import source files while retaining only redacted job metadata."""
    owns_connection = conn is None
    if conn is None:
        conn = sqlite3.connect(db.DB_PATH)
        conn.row_factory = sqlite3.Row
    cutoff = (now or datetime.now(UTC)).isoformat()
    rows = conn.execute(
        """
        SELECT * FROM current_state_import_jobs
        WHERE source_deleted_at IS NULL
          AND source_retention_expires_at IS NOT NULL
          AND source_retention_expires_at <= ?
        """,
        (cutoff,),
    ).fetchall()
    deleted_count = 0
    timestamp = now_iso()
    for row in rows:
        if _delete_import_source(row, conn, timestamp):
            deleted_count += 1
    if owns_connection:
        conn.commit()
        conn.close()
    return deleted_count


def _slug(value: str) -> str:
    return "-".join(part for part in "".join(char.lower() if char.isalnum() else " " for char in value).split() if part) or "item"


def _clean_drawio_value(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split())


def _drawio_geometry(cell: ET.Element) -> dict[str, float]:
    geometry = cell.find("mxGeometry")
    if geometry is None:
        return {"x": 0.0, "y": 0.0}
    return {"x": float(geometry.attrib.get("x", 0) or 0), "y": float(geometry.attrib.get("y", 0) or 0)}


def _normalise_import_layout(nodes: list[dict[str, object]], lanes: dict[str, dict[str, str]], phases: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    """Render imported diagrams into a clean SimpleTS layout rather than preserving draw.io coordinates.

    draw.io stores many node coordinates relative to nested containers. Preserving
    those values creates overlapping cards after import. Instead, keep draw.io
    only as an ordering hint and place nodes on a readable lane/phase grid.
    """
    lane_order = {lane_id: index for index, lane_id in enumerate(lanes.keys())}
    phase_order = {phase_id: index for index, phase_id in enumerate(phases.keys())}
    lane_counters: dict[str, int] = {}
    normalised: list[dict[str, object]] = []
    sorted_nodes = sorted(
        nodes,
        key=lambda node: (
            lane_order.get(str(node.get("lane_id") or ""), 999),
            phase_order.get(str(node.get("phase_id") or ""), 999),
            float(node.get("_source_x", 0)),
            float(node.get("_source_y", 0)),
        ),
    )
    for node in sorted_nodes:
        lane_id = str(node.get("lane_id") or "default")
        lane_index = lane_order.get(str(node.get("lane_id") or ""), 0)
        sequence = lane_counters.get(lane_id, 0)
        lane_counters[lane_id] = sequence + 1
        clean_node = {key: value for key, value in node.items() if not key.startswith("_source_")}
        clean_node["position"] = {"x": 220 + sequence * 280, "y": 140 + lane_index * 190}
        normalised.append(clean_node)
    return normalised


def _convert_drawio_to_draft_map(job_id: str, workspace_id: str, contents: bytes, conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    try:
        root = ET.fromstring(contents.decode("utf-8", errors="ignore"))
    except ET.ParseError:
        return None, "could not read draw.io process-map XML"

    cells = {cell.attrib.get("id"): cell for cell in root.iter("mxCell") if cell.attrib.get("id")}
    if not cells:
        return None, "could not extract process-map steps from uploaded artifact"

    def ancestors(cell: ET.Element) -> list[ET.Element]:
        result: list[ET.Element] = []
        parent_id = cell.attrib.get("parent")
        while parent_id and parent_id in cells and parent_id not in {"0", "1"}:
            parent = cells[parent_id]
            result.append(parent)
            parent_id = parent.attrib.get("parent")
        return result

    def absolute_position(cell: ET.Element) -> dict[str, float]:
        position = _drawio_geometry(cell)
        for ancestor in ancestors(cell):
            ancestor_position = _drawio_geometry(ancestor)
            position["x"] += ancestor_position["x"]
            position["y"] += ancestor_position["y"]
        return position

    title = "AI-imported draw.io current-state map"
    diagram = root.find("diagram")
    if diagram is not None and diagram.attrib.get("name"):
        title = _clean_drawio_value(diagram.attrib.get("name")) or title

    lanes: dict[str, dict[str, str]] = {}
    lane_source_y: dict[str, float] = {}
    phases: dict[str, dict[str, str]] = {}
    phase_source_x: dict[str, float] = {}
    nodes: list[dict[str, object]] = []
    imported_ids: set[str] = set()
    container_styles = ("shape=table", "shape=tableRow", "swimlane", "childLayout=tableLayout")

    for cell_id, cell in cells.items():
        if cell.attrib.get("vertex") != "1":
            continue
        value = _clean_drawio_value(cell.attrib.get("value"))
        if not value:
            continue
        style = cell.attrib.get("style", "")
        if any(token in style for token in container_styles):
            continue
        style_lower = style.lower()
        value_lower = value.lower()
        if "decision" in style_lower or "rhombus" in style_lower:
            node_type = "decision"
        elif "document" in style_lower:
            node_type = "document"
        elif "terminator" in style_lower or value_lower == "start":
            node_type = "start"
        elif value_lower == "end":
            node_type = "end"
        else:
            node_type = "process"
        row_title = ""
        phase_title = "Process"
        for ancestor in ancestors(cell):
            ancestor_style = ancestor.attrib.get("style", "")
            ancestor_value = _clean_drawio_value(ancestor.attrib.get("value"))
            ancestor_position = absolute_position(ancestor)
            if ancestor_value and "shape=tableRow" in ancestor_style:
                row_title = ancestor_value
                lane_source_y[_slug(row_title)] = ancestor_position["y"]
            elif ancestor_value and "swimlane" in ancestor_style:
                phase_title = ancestor_value
                phase_source_x[_slug(phase_title)] = ancestor_position["x"]
        lane_id = _slug(row_title) if row_title else None
        if lane_id:
            lanes.setdefault(lane_id, {"id": lane_id, "title": row_title})
        phase_id = _slug(phase_title)
        phases.setdefault(phase_id, {"id": phase_id, "title": phase_title})
        imported_ids.add(cell_id)
        pos = absolute_position(cell)
        nodes.append({"id": _slug(cell_id), "lane_id": lane_id, "phase_id": phase_id, "title": value, "node_type": node_type, "position": pos, "_source_x": pos["x"], "_source_y": pos["y"]})

    if not nodes:
        return None, "could not extract process-map steps from uploaded artifact"

    lanes = dict(sorted(lanes.items(), key=lambda item: (lane_source_y.get(item[0], 0), item[1]["title"])))
    phases = dict(sorted(phases.items(), key=lambda item: (phase_source_x.get(item[0], 0), item[1]["title"])))
    nodes = _normalise_import_layout(nodes, lanes, phases)

    connectors: list[dict[str, str | None]] = []
    for cell_id, cell in cells.items():
        if cell.attrib.get("edge") != "1":
            continue
        source = cell.attrib.get("source")
        target = cell.attrib.get("target")
        if source in imported_ids and target in imported_ids:
            label = _clean_drawio_value(cell.attrib.get("value")) or None
            connectors.append({"id": _slug(cell_id), "source_node_id": _slug(source), "target_node_id": _slug(target), "label": label})

    return _insert_imported_map(job_id, workspace_id, title, list(lanes.values()), list(phases.values()), nodes, connectors, conn)


def _mermaid_node_type(shape_start: str, shape_end: str, title: str) -> str:
    lower_title = title.lower()
    if {shape_start, shape_end} in ({"{", "}"}, {"{{", "}}"}):
        return "decision"
    if shape_start == "[/" or shape_start == "[\\":
        return "document"
    if lower_title in {"start", "begin"}:
        return "start"
    if lower_title in {"end", "finish", "stop"}:
        return "end"
    return "process"


def _convert_mermaid_to_draft_map(job_id: str, workspace_id: str, contents: bytes, conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    text = contents.decode("utf-8", errors="ignore")
    lanes = {"process": {"id": "process", "title": "Process"}}
    phases = {"process": {"id": "process", "title": "Process"}}
    nodes_by_key: dict[str, dict[str, object]] = {}
    connectors: list[dict[str, str | None]] = []

    def ensure_node(token: str) -> str:
        token = token.strip().strip(";")
        match = re.match(r"^([A-Za-z0-9_\-]+)\s*(\(\[|\[\/|\[\\|\{\{|\{|\(|\[)(.*?)(\]\)|\/\]|\\\]|\}\}|\}|\)|\])$", token)
        if match:
            node_id = _slug(match.group(1))
            shape_start = match.group(2)
            title = (match.group(3) or match.group(1)).strip().strip('"')
            shape_end = match.group(4)
        else:
            simple = re.match(r"^([A-Za-z0-9_\-]+)$", token)
            node_id = _slug(simple.group(1) if simple else token)
            title = simple.group(1) if simple else token
            shape_start = shape_end = ""
        nodes_by_key.setdefault(node_id, {"id": node_id, "lane_id": "process", "phase_id": "process", "title": title, "node_type": _mermaid_node_type(shape_start, shape_end, title), "_source_x": float(len(nodes_by_key)), "_source_y": 0.0})
        return node_id

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("%%") or line.lower().startswith(("flowchart", "graph", "sequence", "classdiagram")):
            continue
        match = re.match(r"(.+?)\s*(?:-->|---|==>|-.->)\s*(?:\|([^|]+)\|\s*)?(.+)", line.rstrip(";"))
        if match:
            source_id = ensure_node(match.group(1))
            target_id = ensure_node(match.group(3))
            label = " ".join((match.group(2) or "").split()) or None
            connectors.append({"id": f"flow-{len(connectors) + 1}", "source_node_id": source_id, "target_node_id": target_id, "label": label})
        elif re.match(r"^[A-Za-z0-9_\-]+", line):
            ensure_node(line)

    if not nodes_by_key:
        return None, "could not extract process-map steps from uploaded artifact"
    nodes = _normalise_import_layout(list(nodes_by_key.values()), lanes, phases)
    return _insert_imported_map(job_id, workspace_id, "Imported Mermaid current-state map", list(lanes.values()), list(phases.values()), nodes, connectors, conn)


def _convert_bpmn_to_draft_map(job_id: str, workspace_id: str, contents: bytes, conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    try:
        root = ET.fromstring(contents.decode("utf-8", errors="ignore"))
    except ET.ParseError:
        return None, "could not read BPMN process-map XML"
    lanes = {"process": {"id": "process", "title": "Process"}}
    phases = {"process": {"id": "process", "title": "Process"}}
    nodes: list[dict[str, object]] = []
    imported_ids: set[str] = set()
    tag_types = {"startEvent": "start", "endEvent": "end", "exclusiveGateway": "decision", "inclusiveGateway": "decision", "parallelGateway": "decision", "task": "process", "userTask": "process", "serviceTask": "process", "manualTask": "process", "scriptTask": "process", "businessRuleTask": "process"}
    for index, element in enumerate(root.iter()):
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in tag_types:
            continue
        element_id = element.attrib.get("id") or f"node-{index}"
        title = _clean_drawio_value(element.attrib.get("name")) or tag.replace("Task", " task").replace("Event", " event")
        node_id = _slug(element_id)
        imported_ids.add(element_id)
        nodes.append({"id": node_id, "lane_id": "process", "phase_id": "process", "title": title, "node_type": tag_types[tag], "_source_x": float(index), "_source_y": 0.0})
    if not nodes:
        return None, "could not extract process-map steps from uploaded artifact"
    connectors: list[dict[str, str | None]] = []
    for index, element in enumerate(root.iter()):
        tag = element.tag.rsplit("}", 1)[-1]
        if tag != "sequenceFlow":
            continue
        source = element.attrib.get("sourceRef")
        target = element.attrib.get("targetRef")
        if source in imported_ids and target in imported_ids:
            connectors.append({"id": _slug(element.attrib.get("id") or f"flow-{index}"), "source_node_id": _slug(source), "target_node_id": _slug(target), "label": _clean_drawio_value(element.attrib.get("name")) or None})
    nodes = _normalise_import_layout(nodes, lanes, phases)
    return _insert_imported_map(job_id, workspace_id, "Imported BPMN current-state map", list(lanes.values()), list(phases.values()), nodes, connectors, conn)


def _convert_import_to_draft_map(job_id: str, workspace_id: str, filename: str, contents: bytes, conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    extension = Path(filename).suffix.lower()
    if extension == ".drawio":
        return _convert_drawio_to_draft_map(job_id, workspace_id, contents, conn)
    if extension in {".mmd", ".mermaid"}:
        return _convert_mermaid_to_draft_map(job_id, workspace_id, contents, conn)
    if extension == ".bpmn":
        return _convert_bpmn_to_draft_map(job_id, workspace_id, contents, conn)

    text = contents.decode("utf-8", errors="ignore")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None, "could not extract process-map steps from uploaded artifact"

    allowed_shapes = {"start", "end", "decision", "process", "document"}
    lanes: dict[str, dict[str, str]] = {}
    phases: dict[str, dict[str, str]] = {}
    nodes: list[dict[str, str]] = []
    connectors: list[dict[str, str | None]] = []
    title_to_id: dict[str, str] = {}

    for index, line in enumerate(lines, start=1):
        if "->" in line:
            left, _, right = line.partition("->")
            target, _, label = right.partition("|")
            source_id = title_to_id.get(left.strip())
            target_id = title_to_id.get(target.strip())
            if source_id and target_id:
                connectors.append({"id": f"flow-{index}", "source_node_id": source_id, "target_node_id": target_id, "label": label.strip() or None})
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            continue
        lane_title, phase_title, node_title = parts[:3]
        node_type = parts[3].lower() if len(parts) > 3 and parts[3].lower() in allowed_shapes else "process"
        lane_id = _slug(lane_title)
        phase_id = _slug(phase_title)
        node_id = _slug(node_title)
        lanes.setdefault(lane_id, {"id": lane_id, "title": lane_title})
        phases.setdefault(phase_id, {"id": phase_id, "title": phase_title})
        title_to_id[node_title] = node_id
        nodes.append({"id": node_id, "lane_id": lane_id, "phase_id": phase_id, "title": node_title, "node_type": node_type, "position": {"x": (index - 1) * 220, "y": 120}})

    if not nodes:
        return None, "could not extract process-map steps from uploaded artifact"

    return _insert_imported_map(job_id, workspace_id, "AI-imported draft current-state map", list(lanes.values()), list(phases.values()), nodes, connectors, conn)


def _insert_map_row(
    conn: sqlite3.Connection,
    workspace_id: str,
    title: str,
    version_ref: str | None,
    map_status: str,
    source_version_id: str | None,
    lanes: list[dict],
    phases: list[dict],
    nodes: list[dict],
    connectors: list[dict],
    comments: list[dict],
) -> str:
    map_id = str(uuid4())
    timestamp = now_iso()
    conn.execute(
        """
        INSERT INTO current_state_maps (
            id, workspace_id, title, version_ref, status, source_version_id, lanes, phases, nodes, connectors, comments, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            map_id,
            workspace_id,
            title,
            version_ref,
            map_status,
            source_version_id,
            _json_dump(lanes),
            _json_dump(phases),
            _json_dump(nodes),
            _json_dump(connectors),
            _json_dump(comments),
            timestamp,
            timestamp,
        ),
    )
    return map_id


def _insert_imported_map(job_id: str, workspace_id: str, title: str, lanes: list[dict], phases: list[dict], nodes: list[dict], connectors: list[dict], conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    timestamp = now_iso()
    comments = [{
        "id": f"cleanup-{job_id}",
        "body": "AI-imported draft requires human cleanup before use; conversion may be incomplete or inaccurate.",
        "node_id": None,
        "version_ref": "ai-import-draft",
        "author": "system",
        "created_at": timestamp,
        "resolved": False,
    }]
    map_id = _insert_map_row(conn, workspace_id, title, "ai-import-draft", "draft", None, lanes, phases, nodes, connectors, comments)
    return map_id, None


def _get_workspace_map(map_id: str, workspace_id: str, conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM current_state_maps WHERE id = ? AND workspace_id = ?",
        (map_id, workspace_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="current-state map not found")
    return row


def _version_family_ids(map_id: str, workspace_id: str, conn: sqlite3.Connection) -> set[str]:
    family = {map_id}
    changed = True
    while changed:
        changed = False
        placeholders = ",".join("?" for _ in family)
        rows = conn.execute(
            f"SELECT id, source_version_id FROM current_state_maps WHERE workspace_id = ? AND (id IN ({placeholders}) OR source_version_id IN ({placeholders}))",
            (workspace_id, *family, *family),
        ).fetchall()
        for row in rows:
            for candidate in (row["id"], row["source_version_id"]):
                if candidate and candidate not in family:
                    family.add(candidate)
                    changed = True
    return family


@import_router.post("", response_model=CurrentStateImportJob, status_code=status.HTTP_201_CREATED)
def upload_current_state_import(
    file: UploadFile = File(),
    actor: WorkspaceActor = Depends(require_any_staff),
    conn: sqlite3.Connection = Depends(get_connection),
) -> CurrentStateImportJob:
    job_id = str(uuid4())
    timestamp = now_iso()
    filename = file.filename or "import.bin"
    file_type = file.content_type or "application/octet-stream"
    source_retention_expires_at = (datetime.now(UTC) + timedelta(hours=IMPORT_SOURCE_RETENTION_HOURS)).isoformat()
    extension = Path(filename).suffix.lower()
    if extension not in ACCEPTED_IMPORT_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported process-map import file type")
    contents = file.file.read()
    if len(contents) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="process-map import file is too large")
    upload_dir = db.DATA_DIR / "current-state-imports" / job_id
    upload_dir.mkdir(parents=True, exist_ok=False)
    storage_path = upload_dir / "source"
    storage_path.write_bytes(contents)
    conn.execute(
        """
        INSERT INTO current_state_import_jobs (
            id, workspace_id, filename_hash, filename_redacted, filename_display, dismissed_at, file_type, uploader, status,
            error_message, temporary_storage_path, source_deleted_at, source_retention_expires_at, result_map_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            actor.workspace.id,
            hashlib.sha256(filename.encode("utf-8")).hexdigest(),
            _redacted_filename(filename),
            _display_filename(filename),
            None,
            file_type,
            actor.user.user_id,
            "pending",
            None,
            str(storage_path),
            None,
            source_retention_expires_at,
            None,
            timestamp,
            timestamp,
        ),
    )
    row = _get_workspace_import_job(job_id, actor.workspace.id, conn)
    map_id, error_message = _convert_import_to_draft_map(job_id, actor.workspace.id, filename, contents, conn)
    completed_at = now_iso()
    _delete_import_source(row, conn, completed_at)
    conn.execute(
        "UPDATE current_state_import_jobs SET status = ?, error_message = ?, result_map_id = ?, updated_at = ? WHERE id = ? AND workspace_id = ?",
        ("failed" if error_message else "succeeded", error_message, map_id, completed_at, job_id, actor.workspace.id),
    )
    conn.commit()
    return _row_to_import_job(_get_workspace_import_job(job_id, actor.workspace.id, conn))


@import_router.get("", response_model=list[CurrentStateImportJob])
def list_current_state_imports(
    actor: WorkspaceActor = Depends(require_any_staff),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[CurrentStateImportJob]:
    rows = conn.execute(
        "SELECT * FROM current_state_import_jobs WHERE workspace_id = ? AND dismissed_at IS NULL ORDER BY created_at",
        (actor.workspace.id,),
    ).fetchall()
    return [_row_to_import_job(row) for row in rows]


@import_router.post("/{job_id}/dismiss", response_model=CurrentStateImportJob)
def dismiss_current_state_import(
    job_id: str,
    actor: WorkspaceActor = Depends(require_any_staff),
    conn: sqlite3.Connection = Depends(get_connection),
) -> CurrentStateImportJob:
    row = _get_workspace_import_job(job_id, actor.workspace.id, conn)
    if row["status"] != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="only failed imports can be dismissed")
    timestamp = now_iso()
    conn.execute(
        "UPDATE current_state_import_jobs SET dismissed_at = ?, updated_at = ? WHERE id = ? AND workspace_id = ?",
        (timestamp, timestamp, job_id, actor.workspace.id),
    )
    conn.commit()
    return _row_to_import_job(_get_workspace_import_job(job_id, actor.workspace.id, conn))


@import_router.post("/{job_id}/retry", response_model=CurrentStateImportJob)
def retry_current_state_import(
    job_id: str,
    actor: WorkspaceActor = Depends(require_any_staff),
    conn: sqlite3.Connection = Depends(get_connection),
) -> CurrentStateImportJob:
    _get_workspace_import_job(job_id, actor.workspace.id, conn)
    timestamp = now_iso()
    conn.execute(
        "UPDATE current_state_import_jobs SET status = ?, error_message = NULL, dismissed_at = NULL, updated_at = ? WHERE id = ? AND workspace_id = ?",
        ("pending", timestamp, job_id, actor.workspace.id),
    )
    conn.commit()
    return _row_to_import_job(_get_workspace_import_job(job_id, actor.workspace.id, conn))


@router.post("", response_model=CurrentStateMap, status_code=status.HTTP_201_CREATED)
def create_current_state_map(
    payload: CurrentStateMapCreate,
    actor: WorkspaceActor = Depends(require_current_state_editor),
    conn: sqlite3.Connection = Depends(get_connection),
) -> CurrentStateMap:
    map_id = _insert_map_row(
        conn,
        actor.workspace.id,
        payload.title.strip(),
        payload.version_ref,
        "draft",
        payload.source_version_id,
        [lane.model_dump() for lane in payload.lanes],
        [phase.model_dump() for phase in payload.phases],
        [node.model_dump() for node in payload.nodes],
        [connector.model_dump() for connector in payload.connectors],
        [comment.model_dump() for comment in payload.comments],
    )
    conn.commit()
    return _row_to_map(_get_workspace_map(map_id, actor.workspace.id, conn))


@router.get("", response_model=list[CurrentStateMap])
def list_current_state_maps(
    actor: WorkspaceActor = Depends(require_any_staff),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[CurrentStateMap]:
    rows = conn.execute(
        "SELECT * FROM current_state_maps WHERE workspace_id = ? AND status != 'archived' ORDER BY created_at",
        (actor.workspace.id,),
    ).fetchall()
    return [_row_to_map(row) for row in rows]


@router.get("/{map_id}", response_model=CurrentStateMap)
def get_current_state_map(
    map_id: str,
    actor: WorkspaceActor = Depends(require_any_staff),
    conn: sqlite3.Connection = Depends(get_connection),
) -> CurrentStateMap:
    return _row_to_map(_get_workspace_map(map_id, actor.workspace.id, conn))


@router.put("/{map_id}", response_model=CurrentStateMap)
def update_current_state_map(
    map_id: str,
    payload: CurrentStateMapUpdate,
    actor: WorkspaceActor = Depends(require_current_state_editor),
    conn: sqlite3.Connection = Depends(get_connection),
) -> CurrentStateMap:
    existing = _get_workspace_map(map_id, actor.workspace.id, conn)
    if existing["status"] == "archived":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="archived current-state map versions cannot be edited")
    family_ids = _version_family_ids(map_id, actor.workspace.id, conn)
    if existing["status"] == "approved":
        placeholders = ",".join("?" for _ in family_ids)
        active_draft = conn.execute(
            f"SELECT id FROM current_state_maps WHERE workspace_id = ? AND id IN ({placeholders}) AND status = 'draft' LIMIT 1",
            (actor.workspace.id, *family_ids),
        ).fetchone()
        if active_draft is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="current-state version already has an active draft")
    version_id = _insert_map_row(
        conn,
        actor.workspace.id,
        payload.title.strip(),
        payload.version_ref,
        "draft",
        map_id,
        [lane.model_dump() for lane in payload.lanes],
        [phase.model_dump() for phase in payload.phases],
        [node.model_dump() for node in payload.nodes],
        [connector.model_dump() for connector in payload.connectors],
        [comment.model_dump() for comment in payload.comments],
    )
    conn.commit()
    return _row_to_map(_get_workspace_map(version_id, actor.workspace.id, conn))


@router.post("/{map_id}/comments", response_model=CurrentStateMap, status_code=status.HTTP_201_CREATED)
def add_current_state_comment(
    map_id: str,
    payload: CurrentStateCommentCreate,
    actor: WorkspaceActor = Depends(require_current_state_editor),
    conn: sqlite3.Connection = Depends(get_connection),
) -> CurrentStateMap:
    existing = _row_to_map(_get_workspace_map(map_id, actor.workspace.id, conn))
    if existing.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="only draft current-state maps can be commented on")
    if payload.node_id is not None and not any(node.id == payload.node_id for node in existing.nodes):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="comment node_id must reference an existing node")
    timestamp = now_iso()
    next_comment = CurrentStateComment(
        id=str(uuid4()),
        body=payload.body.strip(),
        node_id=payload.node_id,
        version_ref=payload.version_ref or existing.version_ref,
        author=actor.user.user_id,
        created_at=timestamp,
        resolved=payload.resolved,
    )
    comments = [*existing.comments, next_comment]
    conn.execute(
        "UPDATE current_state_maps SET comments = ?, updated_at = ? WHERE id = ? AND workspace_id = ?",
        (_json_dump([comment.model_dump() for comment in comments]), timestamp, map_id, actor.workspace.id),
    )
    conn.commit()
    return _row_to_map(_get_workspace_map(map_id, actor.workspace.id, conn))


@router.post("/{map_id}/accept", response_model=CurrentStateMap)
def accept_current_state_map(
    map_id: str,
    actor: WorkspaceActor = Depends(require_current_state_approver),
    conn: sqlite3.Connection = Depends(get_connection),
) -> CurrentStateMap:
    existing = _get_workspace_map(map_id, actor.workspace.id, conn)
    if existing["status"] == "archived":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="archived current-state map versions cannot be approved")
    family_ids = _version_family_ids(map_id, actor.workspace.id, conn)
    placeholders = ",".join("?" for _ in family_ids)
    timestamp = now_iso()
    conn.execute(
        f"UPDATE current_state_maps SET status = 'archived', updated_at = ? WHERE workspace_id = ? AND id IN ({placeholders}) AND status = 'approved' AND id != ?",
        (timestamp, actor.workspace.id, *family_ids, map_id),
    )
    conn.execute(
        "UPDATE current_state_maps SET status = ?, updated_at = ? WHERE id = ? AND workspace_id = ?",
        ("approved", timestamp, map_id, actor.workspace.id),
    )
    conn.commit()
    return _row_to_map(_get_workspace_map(map_id, actor.workspace.id, conn))


@router.get("/{map_id}/versions", response_model=list[CurrentStateMap])
def list_current_state_map_versions(
    map_id: str,
    actor: WorkspaceActor = Depends(require_any_staff),
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[CurrentStateMap]:
    _get_workspace_map(map_id, actor.workspace.id, conn)
    family_ids = _version_family_ids(map_id, actor.workspace.id, conn)
    placeholders = ",".join("?" for _ in family_ids)
    rows = conn.execute(
        f"SELECT * FROM current_state_maps WHERE workspace_id = ? AND id IN ({placeholders}) ORDER BY created_at, updated_at",
        (actor.workspace.id, *family_ids),
    ).fetchall()
    return [_row_to_map(row) for row in rows]


@router.post("/{map_id}/lock", response_model=CurrentStateMap)
def lock_current_state_map(
    map_id: str,
    actor: WorkspaceActor = Depends(require_current_state_approver),
    conn: sqlite3.Connection = Depends(get_connection),
) -> CurrentStateMap:
    return accept_current_state_map(map_id, actor, conn)


@router.post("/{map_id}/duplicate", response_model=CurrentStateMap, status_code=status.HTTP_201_CREATED)
def duplicate_current_state_map(
    map_id: str,
    actor: WorkspaceActor = Depends(require_current_state_editor),
    conn: sqlite3.Connection = Depends(get_connection),
) -> CurrentStateMap:
    existing = _row_to_map(_get_workspace_map(map_id, actor.workspace.id, conn))
    family_ids = _version_family_ids(map_id, actor.workspace.id, conn)
    placeholders = ",".join("?" for _ in family_ids)
    active_draft = conn.execute(
        f"SELECT id FROM current_state_maps WHERE workspace_id = ? AND id IN ({placeholders}) AND status = 'draft' LIMIT 1",
        (actor.workspace.id, *family_ids),
    ).fetchone()
    if active_draft is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="current-state version already has an active draft")
    duplicate_id = _insert_map_row(
        conn,
        actor.workspace.id,
        f"{existing.title} (draft)",
        existing.version_ref,
        "draft",
        existing.id,
        [lane.model_dump() for lane in existing.lanes],
        [phase.model_dump() for phase in existing.phases],
        [node.model_dump() for node in existing.nodes],
        [connector.model_dump() for connector in existing.connectors],
        [comment.model_dump() for comment in existing.comments],
    )
    conn.commit()
    return _row_to_map(_get_workspace_map(duplicate_id, actor.workspace.id, conn))
