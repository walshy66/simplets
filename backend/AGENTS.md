# Backend AGENTS.md

## Purpose

FastAPI service layer for SimpleTS APIs, workspace authority, auth boundaries, intake/review orchestration, connector state, execution status, and retention/deletion behavior.

## Ownership

Owns backend application code in `app/`, backend tests in `tests/`, backend config, Docker/Fly files, and API contracts served by FastAPI.

## Local Contracts

- Enforce workspace scope server-side on every tenant-scoped operation.
- Backend is authoritative for auth, roles, approvals, deletion state, connector state, and execution state.
- Do not persist submitted field data, extracted data, uploaded files, raw PII, or OAuth tokens beyond the retention contract.
- Keep destination failures explicit, visible, and non-destructive.
- Current State V1 permission seams may use all workspace staff for create/edit/import/approve while preserving capability-specific guard names for later configurable role permissions.
- Current State persistence must preserve Draft/Approved/Archived version lineage: approved versions are immutable, active lists exclude archived versions, and version history remains workspace-scoped.
- Do not expose raw OAuth tokens or secrets in responses, logs, snapshots, fixtures, or comments.

## Work Guidance

- Prefer test-first changes for auth, tenancy, retention, approval, connector, and workflow execution behavior.
- Use structured 401/403/validation errors according to the root contract.
- Keep app modules small and boundary-oriented; avoid frontend-derived authority.

## Verification

```bash
cd backend
python -m pytest
```

Run targeted tests first when practical, then the full backend suite for high-risk changes.

## Child DOX Index

- `app/` — FastAPI application modules and domain/service boundaries.
- `tests/` — pytest regression and behavior coverage for backend contracts.
