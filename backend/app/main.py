from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.documents import router as documents_router
from app.documents import workflow_router
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


app.include_router(sessions_router)
app.include_router(documents_router)
app.include_router(workflow_router)
app.include_router(workspaces_router)
