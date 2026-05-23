# SimpleTS

SimpleTS is a local-first MVP dashboard for managing AI coding-agent sessions from a laptop.

## MVP goal

Build a simple browser-based dashboard that can:

- Create coding-agent sessions
- Store session metadata locally
- Start a local process for a session
- Save session logs
- Show session history and logs in the UI

## Current scope

This first version is deliberately local-only.

Included:

- FastAPI backend
- React + Vite + TypeScript frontend
- SQLite persistence
- Local subprocess runner
- Local `data/` and `logs/` folders

Excluded for now:

- Docker worker containers
- NAS deployment
- Multi-user authentication
- Linear automation
- GitHub PR automation
- Multiple harness handoff

## Planned local run flow

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Folder structure

```text
simplets/
  backend/
    app/
      main.py
      db.py
      models.py
      schemas.py
      sessions.py
      runner.py
    requirements.txt
  frontend/
    package.json
    index.html
    src/
      App.tsx
      main.tsx
      api.ts
      components/
        SessionList.tsx
        SessionCreateForm.tsx
        SessionDetail.tsx
  data/
    .gitkeep
  logs/
    .gitkeep
```
