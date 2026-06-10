import json
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import (
    ActivityTag,
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
    created_at: str
    updated_at: str


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1)
    subdomain: str = Field(min_length=1)


class WorkspaceBrandingUpdate(BaseModel):
    logo_url: str | None = None
    primary_color: str | None = None


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


class ReviewRunDetail(ReviewQueueItem):
    source_preview: SourcePreview


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
