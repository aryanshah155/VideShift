"""VibeShift API entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import dataset, notebook, runs
from .store import open_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    store, backend = open_store()
    app.state.store = store
    app.state.store_backend = backend
    from .pipeline.runner import RunManager

    app.state.run_manager = RunManager(store, backend=backend)
    yield


app = FastAPI(title="VibeShift API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
app.include_router(dataset.router, prefix="/api", tags=["dataset"])
app.include_router(notebook.router, prefix="/api", tags=["notebook"])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/store")
def store_info() -> dict:
    return {"backend": app.state.store_backend}
