"""Tests for the pandas engine end-to-end and its results contract."""

from __future__ import annotations

from app.pipeline.pandas_engine import PandasEngine
from app.schemas import RunConfig


def test_engine_run_produces_full_contract(sample_df):
    cfg = RunConfig(k=4, find_best_k=False).normalized()
    logs: list[str] = []
    out = PandasEngine().run(sample_df, cfg, progress=logs.append)

    assert out["engine"] == "pandas"
    assert out["rows_ingested"] == len(sample_df)
    assert out["rows_clean"] <= len(sample_df)
    assert out["inertia"] > 0
    assert out["silhouette"] is not None and -1 <= out["silhouette"] <= 1
    assert len(out["clusters"]) == 4
    assert all("means" in c and c["size"] > 0 for c in out["clusters"])
    assert out["decades"], "expected decade aggregation"
    for d in out["decades"]:
        assert abs(sum(d["shares"].values()) - 100.0) < 0.5, "row shares must sum to ~100%"
    assert len(out["pca_sample"]) > 0 and "x" in out["pca_sample"][0]
    assert set(out["timings"]) == {"clean", "assemble", "kmeans", "pca", "aggregate"}
    assert out["benchmark"]["speedup"] > 0
    assert logs, "progress callback should have been called"


def test_find_best_k_sweep(sample_df):
    cfg = RunConfig(find_best_k=True).normalized()
    out = PandasEngine().run(sample_df, cfg)
    assert out["best_k"] is not None and 2 <= out["best_k"] <= 8
    assert len(out["silhouette_by_k"]) > 0


def test_track_frame_has_assignments(sample_df):
    out = PandasEngine().run(sample_df, RunConfig(k=3).normalized())
    tf = out["track_frame"]
    assert {"id", "name", "artists", "year", "decade", "cluster"}.issubset(tf.columns)
    assert tf["cluster"].between(0, 2).all()
