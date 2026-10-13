"""Tests for the pandas engine end-to-end and its results contract."""

from __future__ import annotations

from app.pipeline.labels import label_map, name_cluster
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


def test_cluster_labels_are_derived_from_the_profile(sample_df):
    """Labels must describe the cluster they are attached to, not its id."""
    out = PandasEngine().run(sample_df, RunConfig(k=4).normalized())
    labels = [c["label"] for c in out["clusters"]]
    assert all(labels), "every cluster needs a label"
    assert len(set(labels)) == len(labels), "labels must be distinguishable"

    for c in out["clusters"]:
        m = c["means"]
        if m.get("instrumentalness", 0) >= 0.5:
            assert c["label"].startswith("Instrumental")
        elif m.get("energy", 0) >= 0.68 and m.get("acousticness", 1) <= 0.30:
            assert c["label"].startswith("High-Energy")

    assert label_map(out["clusters"]) == {
        c["cluster"]: c["label"] for c in out["clusters"]
    }


def test_name_cluster_rule_cascade():
    assert name_cluster({"instrumentalness": 0.8, "energy": 0.3}) == "Instrumental / Ambient"
    assert name_cluster({"energy": 0.9, "acousticness": 0.05}) == "High-Energy Electronic"
    assert name_cluster({"acousticness": 0.7, "energy": 0.3}) == "Acoustic / Organic"
    assert name_cluster({"danceability": 0.7, "valence": 0.7, "energy": 0.6}) == "Bright / Upbeat"
    assert name_cluster({"danceability": 0.65, "valence": 0.3, "energy": 0.55}) == "Rhythmic / Dance"
    assert name_cluster({"energy": 0.3, "valence": 0.2}) == "Mellow / Low-Energy"


def test_track_frame_has_assignments(sample_df):
    out = PandasEngine().run(sample_df, RunConfig(k=3).normalized())
    tf = out["track_frame"]
    assert {"id", "name", "artists", "year", "decade", "cluster"}.issubset(tf.columns)
    assert tf["cluster"].between(0, 2).all()
