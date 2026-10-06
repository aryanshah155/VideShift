"""Unit tests for the Big Data Analytics suite."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.cluster import KMeans

from app.bda import run_bda_analyses
from app.bda import bloom, eda, graph, hdfs, mapreduce, ml_models, nosql, streaming
from app.schema import FEATURE_COLS
from app.schemas import RunConfig
from app.pipeline.prepare import clean_dataframe, to_feature_matrix


@pytest.fixture
def labelled(sample_df) -> pd.DataFrame:
    """Cleaned sample frame with a `cluster` column, as the engines produce."""
    cfg = RunConfig().normalized()
    df = clean_dataframe(sample_df, cfg)
    labels = KMeans(n_clusters=3, n_init=2, random_state=42).fit_predict(
        to_feature_matrix(df, cfg.features)
    )
    df = df.copy()
    df["cluster"] = labels
    return df


def test_hdfs_block_arithmetic():
    df = pd.DataFrame({"id": range(10)})
    out = hdfs.simulate_hdfs(df, path="tracks_features.csv", size_mb=300.0)
    assert out["file"]["blocks"] == 3  # 300 MB at 128 MB blocks
    assert out["file"]["replication"] == 3
    assert out["file"]["path"] == "/vibeshift/raw/tracks_features.csv"
    # the lab manual asks for at least 20 commands
    assert len(out["commands"]) >= 20
    assert len(out["datanodes"]) == 4
    # every block carries one replica per node level, all distinct nodes
    for block in out["blocks_shown"]:
        nodes = [r["node"] for r in block["replicas"]]
        assert len(nodes) == 3
        assert len(set(nodes)) == 3


def test_mapreduce_jobs_and_combiner_savings(labelled):
    out = mapreduce.run_mapreduce(labelled, FEATURE_COLS, row_limit=5_000)
    names = [j["name"] for j in out["jobs"]]
    assert names == ["word_count", "aggregates", "join", "top_n", "inverted_index"]

    wordcount = out["jobs"][0]
    assert wordcount["stats"]["map_output_pairs"] > 0
    # reducer output can never exceed the map output
    assert wordcount["stats"]["output_records"] <= wordcount["stats"]["map_output_pairs"]
    # rows are ranked by value, descending
    counts = [r["value"] for r in wordcount["output"]]
    assert counts == sorted(counts, reverse=True)

    aggregates = out["jobs"][1]
    assert aggregates["stats"]["combine_saved_pct"] > 0  # a combiner did something
    assert set(aggregates["output"][0]["value"]) >= {"count", FEATURE_COLS[0]}


def test_bloom_has_no_false_negatives(labelled):
    out = bloom.run_bloom(labelled, test_pairs=300)
    prod = out["production"]
    assert prod["n"] > 0
    assert prod["m"] > prod["n"]
    assert 0 < prod["theoretical_fpr"] < 0.05
    assert prod["false_negatives"] == 0
    assert prod["inserted_verified_present"].split("/")[0] == prod["inserted_verified_present"].split("/")[1]
    # the lab exercise table classifies every probe word
    statuses = {r["status"] for r in out["lab_exercise"]["tests"]}
    assert statuses <= {"True positive", "False positive", "Not present"}
    assert out["lab_exercise"]["true_positives"] >= 1
    assert len(out["manual_11bit"]["bit_string"]) == 11


def test_graph_metrics_are_consistent(labelled):
    out = graph.run_sna(labelled, FEATURE_COLS, sample_n=60, k_neighbors=3)
    stats = out["stats"]
    assert stats["nodes"] == 60
    assert stats["edges"] > 0
    assert 0 < stats["density"] < 1
    assert stats["components"] >= 1
    assert stats["communities"] >= 1
    assert -1.0 <= stats["modularity"] <= 1.0
    assert len(out["nodes"]) == 60
    assert len(out["edges"]) == stats["edges"]
    # layout coordinates must be finite and inside the unit box
    for node in out["nodes"]:
        for key in ("x", "y", "rx", "ry"):
            assert np.isfinite(node[key]), (node["id"], key)
            assert -0.01 <= node[key] <= 100.01
    assert len(out["degree_histogram"]) >= 1
    assert out["layouts"] == ["force", "degree_ring"]


def test_streaming_windows_and_drift(labelled):
    out = streaming.run_streaming(labelled, FEATURE_COLS)
    stats = out["stats"]
    assert stats["events"] > 0
    assert stats["batches"] >= 1
    assert 0 <= stats["late_pct"] <= 100
    for window in out["windows"]:
        assert set(window["means"]) == set(out["features"])
    for point in out["drift_points"]:
        assert abs(point["z_score"]) > stats["drift_z_threshold"]


def test_ml_supervised_and_model_selection(labelled):
    out = ml_models.run_ml(labelled, FEATURE_COLS, k=3)
    sup = out["supervised"]
    assert sup["split"]["train_rows"] > 0 and sup["split"]["test_rows"] > 0
    assert len(sup["models"]) == 3
    for row in sup["models"]:
        assert 0.0 <= row["accuracy"] <= 1.0
        assert 0.0 <= row["f1"] <= 1.0
    # 2x2 confusion matrix
    assert len(sup["confusion_matrix"]) == 2
    assert all(len(r) == 2 for r in sup["confusion_matrix"])
    assert len(sup["feature_importance"]) == len(FEATURE_COLS)

    elbow = out["elbow"]
    assert len(elbow["k"]) == len(elbow["inertia"])
    assert elbow["inertia"] == sorted(elbow["inertia"], reverse=True)
    assert elbow["elbow_k"] in elbow["k"]

    hier = out["hierarchical"]
    assert len(hier["leaves"]) == hier["rows_used"]
    assert len(hier["segments"]) == (hier["rows_used"] - 1) * 3
    assert hier["max_height"] > 0


def test_eda_correlation_and_outliers(labelled):
    out = eda.run_eda(labelled, FEATURE_COLS)
    for c in FEATURE_COLS:
        assert out["correlation"][c][c] == pytest.approx(1.0)
        assert out["stats"][c]["count"] > 0
        assert out["outliers"][c]["upper"] >= out["outliers"][c]["lower"]
    # correlation must be symmetric
    a, b = FEATURE_COLS[0], FEATURE_COLS[1]
    assert out["correlation"][a][b] == pytest.approx(out["correlation"][b][a])


def test_nosql_falls_back_without_mongo():
    out = nosql.run_nosql(None, "json-fallback")
    assert out["connected"] is False
    assert out["backend"] == "json-fallback"
    assert len(out["commands"]) >= 20


def test_orchestrator_reports_every_analysis(labelled):
    out = run_bda_analyses(labelled, FEATURE_COLS, store=None, store_backend="json-fallback")
    for key in ("hdfs", "mapreduce", "bloom", "graph", "streaming", "ml", "nosql", "eda"):
        assert key in out, key
        assert "error" not in out[key], (key, out[key].get("error"))
    summary = out["summary"]
    assert summary["analyses_ok"] == summary["analyses_total"] == 8
    assert len(summary["experiments_covered"]) == 9
