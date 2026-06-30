# SimpleTS Agent Instructions

## Project identity

SimpleTS is a white-label client portal and workflow orchestration platform for professional services businesses.

Core promise:

> Submit once → review once → distribute everywhere

The previous local AI coding-agent/dashboard direction is obsolete and MUST NOT guide new work.

## Product principles

Follow `constitution.md` for all product, architecture, and implementation decisions.

Non-negotiables:

- Human approval is mandatory before any writeback to destination systems.
- SimpleTS is a pipe, not a permanent database.
- Submitted field data, extracted data, and uploaded files must be purged after successful approval and distribution.
- Minimal audit records must not contain raw PII, submitted values, extracted values, uploaded document contents, or OAuth tokens.
- Workspace isolation is mandatory for all backend reads/writes and UI behavior.
- Backend is authoritative for auth, roles, workspace scope, approval state, deletion state, connector state, and workflow execution.
- Destination failures must be visible, retryable where safe, and must not cause data loss.
- OAuth tokens and secrets must never appear in logs, API responses, comments, snapshots, or source control.

## Current golden path

Prioritise the first end-to-end slice:

```text
Branded web form intake → subscriber review/approval → third-party app distribution
```

Document upload, AI extraction, broader connectors, and advanced workflow templates are secondary unless explicitly prioritised.

## Stack

- Frontend: React, TypeScript, Vite, Clerk
- Backend: FastAPI, Pydantic, pytest
- Workflow engine: embedded/forked Activepieces
- Target DB: Postgres
- Target hosting: Fly.io, Sydney region
- Auth: Clerk
- Connectors: HubSpot and Google Drive first; PandaDoc/Xero later

## Repo structure

- `backend/` — FastAPI backend
- `frontend/` — React/Vite frontend
- `docs/` — product and planning documentation
- `constitution.md` — source of truth for product and architecture rules
- `README.md` — project overview

## Development commands

Backend:

```bash
cd backend
python -m pytest
```

Frontend:

```bash
cd frontend
npm test
npm run build
```

Run relevant tests before and after changes. For high-risk behavior, write or update tests first.

## Test expectations

Mandatory coverage areas include:

- Workspace isolation and cross-workspace access denial
- Role-based authorization
- Human approval gating before writeback
- Data deletion after successful distribution
- Retention when destination distribution fails
- OAuth token encryption/non-exposure
- Connector revoked/disconnected states
- Subdomain-to-workspace routing
- Workflow execution success/failure status

Bug fixes affecting auth, data safety, deletion, connector execution, tenant isolation, or workflow execution require regression tests.

## Coding rules

- Prefer small, releasable vertical slices.
- Keep Activepieces customisations shallow unless there is an explicit product requirement.
- Do not add silent fallbacks for authorization, approval, deletion, connector execution, or tenant scoping.
- Return explicit structured errors for invariant failures.
- Use `401` for unauthenticated requests.
- Use `403` for authenticated users lacking permission.
- Do not use `403` for validation errors.
- Do not log raw PII, submitted form values, uploaded document contents, extracted data, OAuth tokens, or secrets.
- Do not commit secrets or real client PII.
- Use demo/synthetic data only.

## Frontend guidance

- The frontend must not infer or override backend authority.
- Auth, workspace scope, approval state, deletion state, and connector state must come from backend APIs.
- UI must surface connector/distribution failures visibly.
- Avoid permanent client-data archive behavior.

## Backend guidance

- Every workspace-scoped operation must enforce workspace boundaries server-side.
- Connector credentials must be encrypted at rest and workspace-scoped.
- Approval must be attributable to user, timestamp, workspace, and destination set.
- Data must not be deleted while destination pushes are failed, pending, or unresolved.
- Deletion after successful completion must preserve only minimal audit metadata.

## Documentation

When product or architecture behavior changes, update relevant docs in `docs/` and/or `constitution.md`.

Follow `docs/branding/brand-kit.md` as the canonical developer-facing brand contract. Simple Technology Solutions branding is the binding default for platform-owned experiences; workspace/client branding may override only in explicitly tenant-branded contexts.

Do not reintroduce the obsolete local AI coding-agent dashboard direction.

# DOX framework

- DOX is highly performant AGENTS.md hierarchy installed here
- Agent must follow DOX instructions across any edits

## Core Contract

- AGENTS.md files are binding work contracts for their subtrees
- Work products, source materials, instructions, records, assets, and durable docs must stay understandable from the nearest applicable AGENTS.md plus every parent AGENTS.md above it

## Read Before Editing

1. Read the root AGENTS.md
2. Identify every file or folder you expect to touch
3. Walk from the repository root to each target path
4. Read every AGENTS.md found along each route
5. If a parent AGENTS.md lists a child AGENTS.md whose scope contains the path, read that child and continue from there
6. Use the nearest AGENTS.md as the local contract and parent docs for repo-wide rules
7. If docs conflict, the closer doc controls local work details, but no child doc may weaken DOX

Do not rely on memory. Re-read the applicable DOX chain in the current session before editing.

## Update After Editing

Every meaningful change requires a DOX pass before the task is done.

Update the closest owning AGENTS.md when a change affects:

- purpose, scope, ownership, or responsibilities
- durable structure, contracts, workflows, or operating rules
- required inputs, outputs, permissions, constraints, side effects, or artifacts
- user preferences about behavior, communication, process, organization, or quality
- AGENTS.md creation, deletion, move, rename, or index contents

Update parent docs when parent-level structure, ownership, workflow, or child index changes. Update child docs when parent changes alter local rules. Remove stale or contradictory text immediately. Small edits that do not change behavior or contracts may leave docs unchanged, but the DOX pass still must happen.

## Hierarchy

- Root AGENTS.md is the DOX rail: project-wide instructions, global preferences, durable workflow rules, and the top-level Child DOX Index
- Child AGENTS.md files own domain-specific instructions and their own Child DOX Index
- Each parent explains what its direct children cover and what stays owned by the parent
- The closer a doc is to the work, the more specific and practical it must be

## Child Doc Shape

- Create a child AGENTS.md when a folder becomes a durable boundary with its own purpose, rules, responsibilities, workflow, materials, or quality standards
- Work Guidance must reflect the current standards of the project or user instructions; if there are no specific standards or instructions yet, leave it empty
- Verification must reflect an existing check; if no verification framework exists yet, leave it empty and update it when one exists

Default section order:
- Purpose
- Ownership
- Local Contracts
- Work Guidance
- Verification
- Child DOX Index

## Style

- Keep docs concise, current, and operational
- Document stable contracts, not diary entries
- Put broad rules in parent docs and concrete details in child docs
- Prefer direct bullets with explicit names
- Do not duplicate rules across many files unless each scope needs a local version
- Delete stale notes instead of explaining history
- Trim obvious statements, repeated rules, misplaced detail, and warnings for risks that no longer exist

## Closeout

1. Re-check changed paths against the DOX chain
2. Update nearest owning docs and any affected parents or children
3. Refresh every affected Child DOX Index
4. Remove stale or contradictory text
5. Run existing verification when relevant
6. Report any docs intentionally left unchanged and why

## User Preferences

When the user requests a durable behavior change, record it here or in the relevant child AGENTS.md

- Current State V1 should prioritise simplicity: all workspace staff can create/import/edit/approve Current State drafts until configurable approval permissions are introduced; submit-only/non-staff users remain blocked.
- Current State process-map import replaces invoice-style ingestion for workflow mapping: import is available only from Current State, creates a new draft map, uses temporary source files, displays sanitised filenames for operator usability, and starts with supported process-map file types under 25 MB.
- Current State maps use Draft/Approved/Archived lifecycle semantics: drafts are editable, approved maps are immutable, approving a newer draft archives the previous approved version, and archived versions remain in version history rather than the active list.

## Child DOX Index

- `backend/AGENTS.md` — FastAPI service layer, backend app modules, API authority, auth/tenancy, approvals, connectors, retention, and backend tests.
- `frontend/AGENTS.md` — React/Vite SimpleTS UI, frontend models/tests, Clerk-aware views, review/intake UX, and embedded workflow access.
- `docs/AGENTS.md` — Durable SimpleTS product, architecture, planning, and decision documentation.
- `data/AGENTS.md` — Local runtime/upload artifacts and disposable development/demo data.
- `demo/AGENTS.md` — Synthetic demo scenarios and demo-only assets.
- `ReGroup Solutions Templates/AGENTS.md` — ReGroup scenario templates/reference material.
- `front-end-themes/AGENTS.md` — Branding/theme reference assets.
- `logs/AGENTS.md` — Local transient diagnostic logs.

Root-owned paths without child AGENTS.md: `README.md`, `constitution.md`, `CLAUDE.md`, root config/files, and any new top-level folder until a child AGENTS.md is added.