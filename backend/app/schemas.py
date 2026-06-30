import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import (
    ActivityTag,
    ConnectionStatus,
    ConnectorProvider,
    DocumentDeletionStatus,
    FeatureKey,
    Harness,
    ReviewStatus,
    SessionStatus,
    WorkflowRunStatus,
    WorkspaceRole,
)


class SessionCreate(BaseModel):
    title: str = Field(min_length=1)
    repo_path: str | None = None
    harness: Harness = Harness.TEST
    prompt: str | None = None
    model: str | None = None

    @model_validator(mode="after")
    def validate_harness_inputs(self) -> "SessionCreate":
        if self.harness in {Harness.CODEX, Harness.PI}:
            if not self.repo_path or not self.repo_path.strip():
                raise ValueError("repo_path is required for codex and pi sessions")
            if not self.prompt or not self.prompt.strip():
                raise ValueError("prompt is required for codex and pi sessions")
            if not self.model or not self.model.strip():
                raise ValueError("model is required for codex and pi sessions")
        return self


class Session(BaseModel):
    id: str
    title: str
    repo_path: str | None
    harness: Harness
    prompt: str | None
    model: str | None
    status: SessionStatus
    branch_name: str | None
    log_path: str | None
    output_tail: str | None
    error_message: str | None
    created_at: str
    updated_at: str


class SessionLogs(BaseModel):
    session_id: str
    logs: str


class ActivityItem(BaseModel):
    id: str
    session_id: str
    tag: ActivityTag
    body: str = Field(min_length=1)
    created_at: str


class Workspace(BaseModel):
    id: str
    name: str = Field(min_length=1)
    subdomain: str | None = None
    branding_logo_url: str | None = None
    branding_primary_color: str | None = None
    activepieces_project_id: str | None = None
    created_at: str
    updated_at: str


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1)
    subdomain: str = Field(min_length=1)


class WorkspaceBrandingUpdate(BaseModel):
    logo_url: str | None = None
    primary_color: str | None = None


class WorkspaceUserUpsert(BaseModel):
    role: WorkspaceRole


class WorkspaceCanvasUpdate(BaseModel):
    activepieces_project_id: str | None = None


class DriveDatastoreSetup(BaseModel):
    drive_root_id: str = Field(min_length=1)
    invoice_folder_id: str = Field(min_length=1)
    folder_path: str | None = None


class DriveDatastore(BaseModel):
    provider: Literal["google_drive"] = "google_drive"
    drive_root_id: str
    invoice_folder_id: str
    folder_path: str | None = None


class InvoiceUploadGate(BaseModel):
    available: bool
    reason: str | None = None


class ClientContext(BaseModel):
    workspace: Workspace
    drive_datastore: DriveDatastore | None = None
    invoice_upload: InvoiceUploadGate


class ConnectorConnection(BaseModel):
    """Public connection state. Token material is intentionally absent."""

    id: str
    workspace_id: str
    provider: ConnectorProvider
    status: ConnectionStatus
    token_expires_at: str | None = None
    scopes: str | None = None
    external_account_label: str | None = None
    disconnect_reason: str | None = None
    created_at: str
    updated_at: str


class ConnectorCodeExchange(BaseModel):
    code: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1)
    account_label: str | None = None


class ConnectorConnectionUpsert(BaseModel):
    access_token: str = Field(min_length=1)
    refresh_token: str | None = None
    token_expires_at: str | None = None
    scopes: str | None = None
    external_account_label: str | None = None


class WorkspaceUser(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    role: WorkspaceRole
    created_at: str
    updated_at: str


class WorkspaceFeatureFlag(BaseModel):
    workspace_id: str
    feature_key: FeatureKey
    enabled: bool
    updated_at: str


class DocumentMetadata(BaseModel):
    id: str
    workspace_id: str | None = None
    filename: str
    content_type: str | None
    size_bytes: int
    intent: str
    temporary_storage_path: str
    retention_expires_at: str
    deletion_status: DocumentDeletionStatus
    uploaded_at: str
    uploader: str
    is_permanent_archive: bool = False
    drive_file_id: str | None = None
    drive_web_url: str | None = None
    filename_hash: str | None = None
    filename_redacted: str | None = None


class WorkflowRun(BaseModel):
    id: str
    workspace_id: str | None = None
    document_id: str
    intent: str
    status: WorkflowRunStatus
    extraction_status: WorkflowRunStatus | None = None
    extraction_error: str | None = None
    suggested_classification: str | None = None
    extracted_fields: dict[str, Any] | None = None
    review_status: ReviewStatus = ReviewStatus.PENDING
    last_reviewed_by: str | None = None
    last_reviewed_at: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    destination_record_id: str | None = None
    audit_summary: dict[str, Any] | None = None
    created_at: str
    updated_at: str

    @field_validator("extracted_fields", "audit_summary", mode="before")
    @classmethod
    def parse_json_object_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return json.loads(value)
        return value


class ReviewQueueItem(WorkflowRun):
    document: DocumentMetadata


class SourcePreview(BaseModel):
    available: bool
    content: str | None = None
    reason: str | None = None


class DestinationPush(BaseModel):
    id: str
    workflow_run_id: str
    workspace_id: str
    provider: str
    status: str
    destination_record_id: str | None = None
    error_message: str | None = None
    attempted_at: str | None = None
    created_at: str
    updated_at: str


class ApprovalResult(BaseModel):
    workflow_run: "WorkflowRun"
    destination_pushes: list[DestinationPush]
    all_succeeded: bool


class ReviewRunDetail(ReviewQueueItem):
    source_preview: SourcePreview
    destination_pushes: list[DestinationPush] = []


class ReviewFieldsUpdate(BaseModel):
    reviewer: str = Field(min_length=1)
    extracted_fields: dict[str, Any]

    @field_validator("reviewer")
    @classmethod
    def validate_reviewer(cls, value: str) -> str:
        clean_value = value.strip()
        if not clean_value:
            raise ValueError("reviewer is required")
        return clean_value


class ReviewApprovalRequest(BaseModel):
    reviewer: str = Field(min_length=1)
    fields_reviewed: bool

    @field_validator("reviewer")
    @classmethod
    def validate_reviewer(cls, value: str) -> str:
        clean_value = value.strip()
        if not clean_value:
            raise ValueError("reviewer is required")
        return clean_value

    @model_validator(mode="after")
    def validate_fields_reviewed(self) -> "ReviewApprovalRequest":
        if not self.fields_reviewed:
            raise ValueError("extracted data screen must be reviewed before approval")
        return self


class DocumentUploadResult(BaseModel):
    document: DocumentMetadata
    workflow_run: WorkflowRun


class ExtractionPreview(BaseModel):
    fields: dict[str, Any]
    suggested_classification: str | None = None


class CurrentStateLane(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)


class CurrentStatePhase(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)


class CurrentStatePosition(BaseModel):
    x: float = 0
    y: float = 0


class CurrentStateNode(BaseModel):
    id: str = Field(min_length=1)
    lane_id: str | None = None
    phase_id: str | None = None
    title: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    position: CurrentStatePosition | None = None


class CurrentStateConnector(BaseModel):
    id: str = Field(min_length=1)
    source_node_id: str = Field(min_length=1)
    target_node_id: str = Field(min_length=1)
    label: str | None = None


class CurrentStateComment(BaseModel):
    id: str = Field(min_length=1)
    body: str = Field(min_length=1)
    node_id: str | None = None
    version_ref: str | None = None
    author: str | None = None
    created_at: str | None = None
    resolved: bool = False


class CurrentStateCommentCreate(BaseModel):
    body: str = Field(min_length=1)
    node_id: str | None = None
    version_ref: str | None = None
    resolved: bool = False


class CurrentStateMapCreate(BaseModel):
    title: str = Field(min_length=1)
    version_ref: str | None = None
    status: Literal["draft", "approved", "archived"] = "draft"
    source_version_id: str | None = None
    lanes: list[CurrentStateLane] = Field(default_factory=list)
    phases: list[CurrentStatePhase] = Field(default_factory=lambda: [CurrentStatePhase(id="process", title="Process")])
    nodes: list[CurrentStateNode] = Field(default_factory=list)
    connectors: list[CurrentStateConnector] = Field(default_factory=list)
    comments: list[CurrentStateComment] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "CurrentStateMapCreate":
        lane_ids = {lane.id for lane in self.lanes}
        phase_ids = {phase.id for phase in self.phases}
        node_ids = {node.id for node in self.nodes}
        for node in self.nodes:
            if node.lane_id is not None and node.lane_id not in lane_ids:
                raise ValueError("node lane_id must reference an existing lane when provided")
            if node.phase_id is not None and node.phase_id not in phase_ids:
                raise ValueError("node phase_id must reference an existing phase when provided")
        for connector in self.connectors:
            if connector.source_node_id not in node_ids or connector.target_node_id not in node_ids:
                raise ValueError("every connector requires valid source_node_id and target_node_id")
        for comment in self.comments:
            if comment.node_id is not None and comment.node_id not in node_ids:
                raise ValueError("comment node_id must reference an existing node")
        return self


class CurrentStateMap(CurrentStateMapCreate):
    id: str
    workspace_id: str
    created_at: str
    updated_at: str


class CurrentStateMapUpdate(CurrentStateMapCreate):
    pass


class CurrentStateImportJob(BaseModel):
    id: str
    workspace_id: str
    filename_hash: str
    filename_redacted: str
    filename_display: str | None = None
    dismissed_at: str | None = None
    file_type: str
    uploader: str
    status: Literal["pending", "succeeded", "failed"]
    error_message: str | None = None
    result_map_id: str | None = None
    created_at: str
    updated_at: str
