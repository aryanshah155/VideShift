"""Dataset + engine status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..pipeline.engines import engine_status
from ..pipeline.ingest import dataset_status
from ..schemas import DatasetStatus, EngineStatus

router = APIRouter()


@router.get("/dataset/status", response_model=DatasetStatus)
def dataset(refresh: bool = False):
    """Dataset presence + size + real min/max year (cached scan)."""
    return dataset_status(refresh=refresh)


@router.get("/concepts")
def concepts(request: Request, run_id: str | None = None):
    """The Big Data Analytics concept registry, optionally annotated with the
    evidence collected by a specific run."""
    from .concepts import concepts_payload

    return concepts_payload(request, run_id)


@router.get("/engine", response_model=EngineStatus)
def engine():
    return engine_status()
