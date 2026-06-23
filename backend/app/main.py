from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.connections import router as connections_router
from app.current_state import import_router as current_state_import_router
from app.current_state import router as current_state_router
from app.documents import router as documents_router
from app.documents import workflow_router
from app.intake import router as submissions_router
from app.sessions import router as sessions_router
from app.workspaces import router as workspaces_router

app = FastAPI(title="SimpleTS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


workspace_branding_dir = Path("data/workspace-branding")
workspace_branding_dir.mkdir(parents=True, exist_ok=True)
app.mount("/workspace-branding", StaticFiles(directory=workspace_branding_dir), name="workspace-branding")


app.include_router(sessions_router)
app.include_router(current_state_router)
app.include_router(current_state_import_router)
app.include_router(documents_router)
app.include_router(workflow_router)
app.include_router(workspaces_router)
app.include_router(connections_router)
app.include_router(submissions_router)
