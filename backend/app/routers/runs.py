"""Run lifecycle endpoints."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from ..pipeline import tracks as track_store
from ..pipeline.ingest import dataset_profile
from ..schemas import RunConfig, TrackPage

router = APIRouter()


def _manager(request: Request):
    return request.app.state.run_manager


@router.post("")
def create_run(request: Request, config: RunConfig):
    # Mirror the Dashboard's dataset-derived min/max so a hand-crafted request
    # cannot ask for a year window the dataset cannot satisfy.
    profile = dataset_profile()
    cfg = config.bounded(profile.get("year_min"), profile.get("year_max")).model_dump()
    run_id = _manager(request).start_run(cfg)
    return {"id": run_id, "state": "running"}


@router.get("")
def list_runs(request: Request, limit: int = 25):
    return _manager(request).list_runs(limit)


@router.get("/{run_id}")
def run_status(request: Request, run_id: str):
    doc = _manager(request).get_status(run_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return doc


@router.get("/{run_id}/results")
def run_results(request: Request, run_id: str):
    doc = _manager(request).get_status(run_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if doc.get("state") != "done":
        raise HTTPException(status_code=409, detail=f"Run state is '{doc.get('state')}'")
    path = Path(track_store._runs_dir()) / run_id / "results.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Results file missing")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/{run_id}/bloom")
def run_bloom(request: Request, run_id: str, term: str = ""):
    """Exp.6 in the UI: ask the run's Bloom filter about a search term."""
    doc = _manager(request).get_status(run_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if doc.get("state") != "done":
        raise HTTPException(status_code=409, detail=f"Run state is '{doc.get('state')}'")
    verdict = track_store.bloom_lookup(run_id, term)
    if verdict is None:
        raise HTTPException(status_code=404, detail="Artist index unavailable for this run")
    return verdict


@router.get("/{run_id}/tracks", response_model=TrackPage)
def run_tracks(
    request: Request,
    run_id: str,
    search: str | None = None,
    cluster: int | None = None,
    decade: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    doc = _manager(request).get_status(run_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if doc.get("state") != "done":
        raise HTTPException(status_code=409, detail=f"Run state is '{doc.get('state')}'")
    return track_store.query_tracks(
        run_id, search=search, cluster=cluster, decade=decade, page=page, page_size=page_size
    )
