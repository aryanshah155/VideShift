"""Pydantic models for API requests and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

FEATURES: list[str] = [
    "danceability",
    "energy",
    "valence",
    "tempo",
    "acousticness",
    "instrumentalness",
    "loudness",
    "speechiness",
]


class RunConfig(BaseModel):
    """User-tunable configuration for one pipeline run."""

    k: int = Field(default=5, ge=2, le=12, description="Number of acoustic clusters")
    year_from: int = Field(default=1960, ge=1900, le=2026)
    year_to: int = Field(default=2023, ge=1900, le=2026)
    features: list[str] = Field(default_factory=lambda: list(FEATURES))
    find_best_k: bool = Field(
        default=False,
        description="Sweep k=2..8 and pick the best silhouette score before clustering",
    )
    sample_fraction: float = Field(
        default=1.0,
        ge=0.05,
        le=1.0,
        description="Fraction of rows to sample before clustering (speed knob)",
    )

    def normalized(self) -> "RunConfig":
        data = self.model_copy()
        if data.year_to < data.year_from:
            data.year_from, data.year_to = data.year_to, data.year_from
        valid = [f for f in data.features if f in FEATURES]
        data.features = valid or list(FEATURES)
        return data


class StageInfo(BaseModel):
    name: str
    status: Literal["pending", "running", "done", "failed"] = "pending"
    seconds: float | None = None
    detail: str = ""


class RunStatus(BaseModel):
    id: str
    state: Literal["queued", "running", "done", "failed"]
    engine: str
    config: RunConfig
    stages: list[StageInfo]
    current_stage: str | None = None
    error: str | None = None
    created_at: str
    finished_at: str | None = None


class Benchmark(BaseModel):
    label_a: str
    label_b: str
    seconds_a: float
    seconds_b: float
    speedup: float
    note: str


class ClusterProfile(BaseModel):
    cluster: int
    size: int
    share_pct: float
    label: str
    means: dict[str, float]


class DecadeRow(BaseModel):
    decade: int
    total: int
    shares: dict[str, float]


class RunResults(BaseModel):
    run_id: str
    engine: str
    config: RunConfig
    rows_ingested: int
    rows_clean: int
    total_seconds: float
    inertia: float | None = None
    silhouette: float | None = None
    best_k: int | None = None
    silhouette_by_k: dict[str, float] = Field(default_factory=dict)
    clusters: list[ClusterProfile]
    decades: list[DecadeRow]
    pca_sample: list[dict[str, Any]]
    feature_trends: dict[str, dict[str, float]]
    benchmark: Benchmark | None = None


class TrackPage(BaseModel):
    total: int
    page: int
    page_size: int
    tracks: list[dict[str, Any]]


class DatasetStatus(BaseModel):
    found: bool
    path: str
    size_mb: float | None = None
    message: str


class EngineStatus(BaseModel):
    engine: Literal["spark", "pandas"]
    spark_available: bool
    reason: str
