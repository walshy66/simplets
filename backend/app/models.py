from enum import StrEnum


class SessionStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERRORED = "errored"


class Harness(StrEnum):
    TEST = "test"
    CODEX = "codex"
    PI = "pi"


class ActivityTag(StrEnum):
    COMMENT = "comment"
    NOTE = "note"
    ATTACHMENT = "attachment"
    HANDOFF = "handoff"
    STATUS = "status"
    PROMPT = "prompt"
    BRANCH = "branch"


class WorkspaceRole(StrEnum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    OPERATOR = "operator"


class FeatureKey(StrEnum):
    WORKFLOW_AUTOMATION = "workflow_automation"


class ConnectorProvider(StrEnum):
    HUBSPOT = "hubspot"
    GOOGLE_DRIVE = "google_drive"
    PANDADOC = "pandadoc"
    XERO = "xero"
    MOCK = "mock"


class ConnectionStatus(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class DocumentDeletionStatus(StrEnum):
    RETAINED = "retained"
    DELETED = "deleted"


class WorkflowRunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    ERRORED = "errored"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    APPROVED = "approved"
