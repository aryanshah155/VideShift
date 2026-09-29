"""Notebook export endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from ..notebook_export import build_notebook, notebook_to_bytes
from ..pipeline import tracks as track_store

router = APIRouter()


@router.get("/runs/{run_id}/notebook")
def export_notebook(request: Request, run_id: str):
    doc = request.app.state.run_manager.get_status(run_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Run not found")

    results = None
    if doc.get("state") == "done":
        path = track_store._runs_dir() / run_id / "results.json"
        if path.exists():
            import json

            results = json.loads(path.read_text(encoding="utf-8"))

    notebook = build_notebook(doc.get("config", {}), results)
    filename = f"vibeshift_{run_id}.ipynb"
    return Response(
        content=notebook_to_bytes(notebook),
        media_type="application/x-ipynb+json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
