"""Dataset + engine status endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from ..pipeline.engines import engine_status
from ..pipeline.ingest import dataset_status
from ..schemas import DatasetStatus, EngineStatus

router = APIRouter()


@router.get("/dataset/status", response_model=DatasetStatus)
def dataset():
    return dataset_status()


@router.get("/engine", response_model=EngineStatus)
def engine():
    return engine_status()
