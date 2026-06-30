# SimpleTS

SimpleTS is a white-label client portal and workflow orchestration platform built on Activepieces as the workflow engine.

It helps professional services businesses stop double-handling data across multiple applications. End-clients submit information once through a branded portal; subscriber staff review and approve it; SimpleTS then distributes the approved data into the business systems the subscriber already uses.

## Product direction

SimpleTS is being built as an operational automation platform, not as a local coding-agent dashboard.

The core product promise is:

```text
Submit once → review once → distribute everywhere
```

SimpleTS acts as the front door for client data intake and the pipe between intake, review, and third-party systems. It is not intended to become a permanent client document archive or long-term PII database.

## Primary users

- **End-clients** — submit forms and documents through a branded portal.
- **Subscriber staff** — review, correct, approve, and monitor submitted data.
- **Subscriber admins** — manage users, connected apps, workflow configuration, and branding.
- **STS platform admins** — manage subscriber workspaces and platform operations.

## Core modules

1. **Workflow Canvas**  
   Subscribers configure how data moves through their business using an embedded Activepieces-powered canvas. Activepieces should be invisible to users; the experience is branded as SimpleTS.

2. **Document Intake**  
   End-clients can upload digital documents such as invoices, PDFs, images, ATO notices, or supporting files. This is a core platform capability, but it is secondary to the first web-form intake slice.

3. **Data Extraction**  
   SimpleTS extracts, validates, normalises, and prepares structured data from intake sources. Initial work focuses on structured web-form submissions. Document extraction uses an STS Extract Activepieces piece backed by Claude API when that slice is implemented.

4. **Data Distribution**  
   SimpleTS pushes approved data into connected third-party applications such as HubSpot, Google Drive, PandaDoc, Xero, Microsoft SharePoint/OneDrive, MYOB, and future client-specific systems.

## First golden path

The first product slice is:

```text
Branded web form intake → subscriber review/approval → third-party app distribution
```

This means the initial platform should allow a subscriber to:

- Provide a branded intake portal for their end-clients
- Capture structured data through a hardcoded first-client form
- Save in-progress draft state locally in the end-client browser for v1
- Show submitted data in a subscriber review queue
- Allow staff to correct fields before approval
- Push approved data into configured destination apps
- Track success, failure, retry state, and minimal audit metadata

Document upload and AI extraction remain part of the wider architecture, but the first end-to-end path is web-form data intake.

## Key product rules

- **Human approval is mandatory** before any data is written to destination systems.
- **No silent writeback** — destination failures must be visible, retryable, and must not lose submitted data.
- **Zero retention after completion** — once all destination pushes succeed, uploaded files and extracted/submitted field data are purged from STS storage.
- **Minimal audit only** — retain who approved, when approval happened, and which destinations received data; do not retain field values in the audit record.
- **Workspace isolation is mandatory** — each subscriber has isolated users, branding, workflows, connected apps, tokens, and data.
- **STS is a pipe, not a database** — store configuration and operational metadata, not long-term client PII or financial records.

## Platform architecture direction

Planned platform foundations:

- **Frontend:** React-based STS UI and branded client portal
- **Backend:** FastAPI service layer for STS-specific APIs and orchestration boundaries
- **Workflow engine:** Forked/self-hosted Activepieces embedded inside STS
- **Database:** Postgres for workspace configuration, workflow metadata, encrypted OAuth tokens, and minimal audit records
- **Auth:** Clerk for subscriber staff, end-clients, and platform admins
- **Hosting:** Fly.io, Sydney region, Docker-native deployment
- **Domains:** wildcard subscriber subdomains such as `clientname.simplets.com.au`
- **AI extraction:** Claude API through a custom STS Extract Activepieces piece

## Activepieces role

Activepieces provides the workflow canvas, connector model, and execution foundation.

SimpleTS-specific work should focus on:

- Branded client portal and intake experiences
- Workspace isolation and subdomain routing
- Subscriber review and approval flows
- Data validation and transformation rules
- Custom STS extraction behavior
- Connector configuration and per-workspace OAuth lifecycle
- Audit, deletion, failure visibility, and operational controls

Keep Activepieces customisations shallow where possible: branding, feature control, embedding, and custom pieces. Avoid deep structural changes unless there is a clear SimpleTS product requirement.

## Initial connector priorities

For the first client/demo path, connector priority is:

1. **HubSpot** — contact and deal creation
2. **Google Drive** — folder creation and file storage
3. **PandaDoc** — onboarding document generation
4. **Xero** — contact and invoice creation

OAuth tokens must be stored encrypted per workspace, never exposed in API responses or logs, and refreshed or marked disconnected deliberately.

## Near-term scope

Included in the near-term direction:

- Activepieces fork configured as the embedded workflow engine
- Fly.io deployment baseline
- Clerk authentication
- Workspace isolation and branded subdomain routing
- Hardcoded first-client intake form
- Subscriber review and approval screen
- Centralised OAuth token management
- HubSpot and Google Drive connector paths
- Zero-retention deletion behavior after successful approval/distribution

Planned but secondary:

- Digital invoice/document upload
- Claude-backed document extraction
- PandaDoc and Xero connector completion
- More advanced workflow templates
- Self-serve workflow-canvas refinement

Out of scope for v1:

- Permanent document archive
- Auto-writeback without human approval
- Server-side draft storage for incomplete forms
- Drag-and-drop form builder
- Email ingestion
- Watched folder ingestion
- NAS/self-hosted subscriber deployment
- Real client PII in early demos

## Current build stance

This repository should be treated as a clean build toward the new SimpleTS platform direction.

Legacy references to the previous local AI coding-agent session dashboard are obsolete and should not guide new architecture or product decisions.

## Related planning docs

- [`docs/prd-sts-orchestration-platform.md`](docs/prd-sts-orchestration-platform.md) — current product PRD and implementation decisions

## Getting Started

### Prerequisites

- Python 3.13+
- Node.js 18+
- npm or yarn

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run tests to verify setup:
   ```bash
   python -m pytest
   ```

5. Start the backend server:
   ```bash
   python -m uvicorn app.main:app --reload
   ```
   The backend will run on `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```
   The frontend will typically run on `http://localhost:5173`

### Configuration

Before running the application, ensure you have the required environment variables set:

- **Backend**: Update `.env` files in `backend/` with Clerk API keys and other configuration
- **Frontend**: Update `.env` files in `frontend/` with API endpoints and Clerk configuration

### Running Tests

**Backend:**
```bash
cd backend
python -m pytest
```

**Frontend:**
```bash
cd frontend
npm test
```

## Development notes

Local setup, package structure, and run commands should be updated as the Activepieces fork is integrated and the clean build structure stabilises.
