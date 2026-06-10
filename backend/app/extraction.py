import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.models import WorkflowRunStatus


@dataclass(frozen=True)
class ExtractionRequest:
    document_id: str
    filename: str
    content_type: str | None
    intent: str
    content: bytes


@dataclass(frozen=True)
class ExtractionResult:
    fields: dict[str, Any]
    suggested_classification: str | None = None


class ExtractionProvider(Protocol):
    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        ...


class DemoExtractionProvider:
    """Deterministic local provider for synthetic/demo document extraction."""

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        text = request.content.decode("utf-8", errors="replace").strip()
        preview = text[:500]
        fields: dict[str, Any] = {
            "intent": request.intent,
            "filename": request.filename,
            "summary": preview or "No readable text found.",
        }
        if request.intent == "extract_actions":
            fields["action_items"] = self._extract_action_items(text)
        elif request.intent == "review":
            fields["review_notes"] = ["Review extracted content before any approval or writeback."]

        return ExtractionResult(fields=fields, suggested_classification=self._classify(request.filename, text))

    def _extract_action_items(self, text: str) -> list[str]:
        action_items = [line.strip(" -\t") for line in text.splitlines() if line.strip().lower().startswith(("todo", "action", "follow up"))]
        return action_items or ["Review document and confirm next action."]

    def _classify(self, filename: str, text: str) -> str:
        lowered = f"{filename}\n{text}".lower()
        if "invoice" in lowered:
            return "invoice"
        if "contract" in lowered or "agreement" in lowered:
            return "agreement"
        if "note" in lowered or "meeting" in lowered:
            return "notes"
        return "demo_document"


def get_extraction_provider() -> ExtractionProvider:
    return DemoExtractionProvider()


class ExtractionService:
    def __init__(self, conn: sqlite3.Connection, provider: ExtractionProvider):
        self.conn = conn
        self.provider = provider

    def run(self, workflow_run_id: str, workspace_id: str | None = None) -> sqlite3.Row | None:
        if workspace_id is None:
            workflow_run = self.conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (workflow_run_id,)).fetchone()
        else:
            workflow_run = self.conn.execute(
                "SELECT * FROM workflow_runs WHERE id = ? AND workspace_id = ?", (workflow_run_id, workspace_id)
            ).fetchone()
        if workflow_run is None:
            return None

        document = self.conn.execute("SELECT * FROM documents WHERE id = ?", (workflow_run["document_id"],)).fetchone()
        if document is None:
            self._mark_error(workflow_run_id, "document not found")
            return self.conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (workflow_run_id,)).fetchone()

        path = Path(document["temporary_storage_path"])
        try:
            content = path.read_bytes()
            result = self.provider.extract(
                ExtractionRequest(
                    document_id=document["id"],
                    filename=document["filename"],
                    content_type=document["content_type"],
                    intent=workflow_run["intent"],
                    content=content,
                )
            )
        except Exception as exc:  # Provider and storage failures must be visible on the run.
            self._mark_error(workflow_run_id, str(exc))
        else:
            self.conn.execute(
                """
                UPDATE workflow_runs
                SET status = ?, extraction_status = ?, extraction_error = NULL,
                    suggested_classification = ?, extracted_fields = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    WorkflowRunStatus.COMPLETED.value,
                    WorkflowRunStatus.COMPLETED.value,
                    result.suggested_classification,
                    json.dumps(result.fields),
                    workflow_run_id,
                ),
            )
            self.conn.commit()

        return self.conn.execute("SELECT * FROM workflow_runs WHERE id = ?", (workflow_run_id,)).fetchone()

    def _mark_error(self, workflow_run_id: str, error: str) -> None:
        self.conn.execute(
            """
            UPDATE workflow_runs
            SET status = ?, extraction_status = ?, extraction_error = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (WorkflowRunStatus.ERRORED.value, WorkflowRunStatus.ERRORED.value, error, workflow_run_id),
        )
        self.conn.commit()
