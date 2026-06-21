# SimpleTS Constitution (v0.1.0)

## Purpose, Users & Scope

SimpleTS is a white-label client portal and workflow orchestration platform for professional services businesses.

Its product promise is:

```text
Submit once → review once → distribute everywhere
```

SimpleTS helps subscribers stop double-handling client data across multiple business applications. End-clients submit information once through a branded portal; subscriber staff review and approve it; SimpleTS distributes the approved data to configured third-party systems.

### Primary users

- **End-clients** — submit forms and documents through a branded subscriber portal.
- **Subscriber staff** — review, correct, approve, and monitor submitted data.
- **Subscriber admins** — manage users, connected apps, workflow configuration, and branding.
- **STS platform admins** — manage workspaces and platform operations.

### Scope of this repo

This repository governs the SimpleTS operational platform, including:

- Branded subscriber portals on workspace subdomains.
- Structured web-form data intake.
- Subscriber review and approval flows.
- Workflow orchestration using embedded Activepieces.
- Third-party connector configuration and data distribution.
- OAuth token lifecycle management.
- Workspace isolation and role-based access control.
- Zero-retention data deletion after successful completion.
- Minimal audit records for compliance and operations.

The previous local AI coding-agent dashboard direction is obsolete and MUST NOT guide new product, architecture, or implementation decisions.

---

## Core Principles

### I. Submit Once, Review Once, Distribute Everywhere (NON-NEGOTIABLE)

Every feature MUST reduce duplicate data entry, simplify client intake, or improve safe data distribution.

Work MUST anchor to an explicit user journey and observable success criteria. Features that add complexity without improving intake, review, distribution, reliability, or configuration are out of scope unless explicitly approved.

---

### II. STS Is a Pipe, Not a Database (NON-NEGOTIABLE)

SimpleTS MUST NOT become a permanent store for end-client PII, financial data, or uploaded documents.

STS MAY store:

- Workspace configuration.
- User/account metadata required for access control.
- Workflow definitions and mappings.
- Encrypted OAuth tokens scoped to a workspace.
- Operational execution status.
- Minimal audit records.

STS MUST purge submitted field data, extracted data, and uploaded source files after successful approval and distribution to all required destinations.

Minimal audit records MUST NOT include submitted field values, extracted values, document contents, or raw PII/financial data.

---

### III. Human Approval Before Writeback (NON-NEGOTIABLE)

No client-submitted or AI-extracted data may be written to a destination system without explicit subscriber approval.

- Auto-writeback is prohibited for v1.
- Reviewer corrections MUST be captured before approval.
- Approval MUST be attributable to a user, timestamp, workspace, and destination set.
- If any destination push fails, data MUST NOT be deleted until the failure is resolved or explicitly discarded by an authorised user.

---

### IV. Workspace Isolation & Tenant Boundaries (NON-NEGOTIABLE)

Each subscriber workspace is an isolation boundary.

Workspace-scoped data includes:

- Users and roles.
- Branding and subdomain configuration.
- Forms, workflows, mappings, and connector configuration.
- OAuth tokens and connector state.
- Intake submissions, review queues, execution state, and audit records.

All backend reads and writes MUST be workspace-scoped. A user authenticated to workspace A MUST NOT be able to access workspace B data through UI state, API parameters, connector configuration, subdomain routing, or workflow execution.

Subdomain routing such as `clientname.simplets.com.au` MUST resolve to exactly one workspace.

---

### V. Backend Authority & Explicit Failure Semantics (NON-NEGOTIABLE)

The backend is the authority for workspace scoping, role permissions, approval state, deletion state, connector state, and workflow execution boundaries.

The frontend MUST NOT infer, repair, bypass, or silently override backend authority.

- Unauthenticated requests MUST return 401.
- Authenticated users without permission MUST return 403.
- Validation errors MUST NOT return 403.
- Invariant violations MUST fail explicitly with structured errors.
- Silent fallback, partial success, or best-guess behavior is prohibited for approval, deletion, authorization, and connector execution.

---

### VI. STS Brand Hierarchy

Simple Technology Solutions branding is the authoritative default for platform-owned experiences. Workspace/client branding may override only in tenant-branded contexts and must not weaken platform authority, data safety, approval, retention, or workspace isolation rules.

---

### VII. Activepieces Is the Workflow Engine Boundary

Activepieces provides the workflow canvas, connector model, and execution foundation.

SimpleTS MUST NOT rebuild workflow-engine capabilities that Activepieces already provides well unless an explicit product requirement justifies it.

Activepieces customisations SHOULD remain shallow:

- Branding removal/replacement.
- STS embedding and navigation integration.
- Feature visibility/control.
- Workspace scoping integration.
- Custom STS pieces and connectors.

Deep fork changes MUST be documented with rationale, risk, and upstream-merge impact.

Activepieces branding MUST NOT be visible to subscribers or end-clients in the STS product experience.

---

### VIII. OAuth, Secrets & Connector Safety (NON-NEGOTIABLE)

Connector credentials are security-critical infrastructure.

- OAuth tokens MUST be encrypted at rest and scoped to a workspace.
- Raw tokens MUST NOT appear in logs, API responses, UI output, comments, test snapshots, or error payloads.
- Token refresh MUST be handled deliberately.
- Revoked or invalid tokens MUST surface as a disconnected connector state.
- Workflows depending on disconnected connectors MUST pause or fail visibly; they MUST NOT silently continue.
- Destination API failures MUST be visible, retryable where safe, and must not cause data loss.
- Retries MUST be deterministic and must not create duplicate destination records unless idempotency rules explicitly allow it.

Secrets MUST stay out of source control.

---

### IX. Test-First Reliability

New behavior SHOULD begin with failing automated tests. For high-risk platform behavior, tests are mandatory before merge.

Mandatory test areas:

- Workspace isolation and cross-workspace access denial.
- Role-based authorization.
- Human approval gating before writeback.
- Data deletion after successful distribution.
- Retention when destination distribution fails.
- OAuth token encryption/non-exposure.
- Connector revoked/disconnected states.
- Subdomain-to-workspace routing.
- Workflow execution success/failure status.

Bug fixes MUST include regression tests when the bug affected data safety, authorization, deletion, connectors, workflow execution, or tenant isolation.

---

### X. Observability & Operational Recovery

Data movement must be observable, auditable, and recoverable.

Changes that affect intake, approval, workflow execution, connectors, deletion, or auth MUST include meaningful logs and clear error states.

Operational records SHOULD answer:

- Which workspace initiated the run?
- Which user approved it?
- Which destinations were targeted?
- Which destinations succeeded or failed?
- Whether data was retained, deleted, or awaiting retry/discard?

Logs MUST NOT include raw PII, submitted field values, uploaded document contents, or OAuth tokens.

---

### XI. Incremental, Releasable Slices

Work MUST be broken into independently valuable slices that can be tested and demonstrated.

The first golden path is:

```text
Branded web form intake → subscriber review/approval → third-party app distribution
```

Document upload, OCR/extraction, advanced workflow templates, and broader connector coverage are valid platform capabilities, but they MUST NOT derail the first end-to-end web-form intake path unless explicitly reprioritised.

---

## Infrastructure & Stack Authority

The current platform direction is:

- **Frontend:** React-based STS UI and branded client portal.
- **Backend:** FastAPI service layer for STS-specific APIs and orchestration boundaries.
- **Workflow engine:** forked/self-hosted Activepieces embedded inside STS.
- **Database:** Postgres for workspace configuration, workflow metadata, encrypted OAuth tokens, execution metadata, and minimal audit records.
- **Auth:** Clerk for subscriber staff, end-clients, and platform admins.
- **Hosting:** Fly.io, Sydney region, Docker-native deployment.
- **Domains:** wildcard subscriber subdomains such as `clientname.simplets.com.au`.
- **AI extraction:** Claude API through a custom STS Extract Activepieces piece.

Major deviations from this stack MUST be documented before implementation.

---

## Connector Priority

Initial connector priority is:

1. HubSpot — contact and deal creation.
2. Google Drive — folder creation and file storage.
3. PandaDoc — onboarding document generation.
4. Xero — contact and invoice creation.

Additional connectors are allowed when they support a real subscriber workflow and follow the OAuth, isolation, testing, and observability rules above.

---

## UI & Product Experience Requirements

- Subscribers and end-clients MUST experience the product as SimpleTS, not Activepieces.
- Subscriber portals MUST support workspace branding.
- Review screens MUST make flagged, missing, low-confidence, or failed fields obvious.
- Approval actions MUST be explicit and hard to trigger accidentally.
- Destination failures MUST be understandable and actionable by subscriber staff/admins.
- Accessibility and keyboard usability SHOULD be considered from the first implementation, especially for forms, review queues, and approval actions.

---

## Documentation & Review Discipline

Before implementation, feature work SHOULD identify:

- The user journey it supports.
- The workspace/role boundary involved.
- Whether submitted data, documents, tokens, or audit records are affected.
- The deletion/retention behavior.
- The connector failure behavior.
- The tests required for data safety and authorization.

Before merge, review MUST confirm:

- The implementation matches the README, PRD, Linear issue, and this constitution.
- Workspace isolation is preserved.
- Backend authority is preserved.
- No secrets or raw tokens are exposed.
- No long-term PII/financial data retention was introduced unintentionally.
- Required tests were added and run.

Intentional deviations from this constitution MUST be documented with rationale and approved before implementation.

---

## Related Documents

- [`README.md`](README.md) — project overview and build direction.
- [`docs/prd-sts-orchestration-platform.md`](docs/prd-sts-orchestration-platform.md) — product PRD and implementation decisions.
