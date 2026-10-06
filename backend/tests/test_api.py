"""Integration tests exercising the API against a temp dataset."""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, sample_df, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sample_df.to_csv(data_dir / "tracks_features.csv", index=False)

    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("VIBESHIFT_DATA_DIR", str(data_dir))
    # Isolate the run registry too: without this, tests write run documents into
    # the real MongoDB while their artifacts sit in a temp directory, leaving
    # broken entries in the app's run history.
    monkeypatch.setenv("VIBESHIFT_MONGO_DB", "vibeshift_test")
    get_settings.cache_clear()

    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_dataset_status_found(client):
    r = client.get("/api/dataset/status")
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["size_mb"] > 0


def test_dataset_status_reports_year_range(client, sample_df):
    """The Dashboard's year-input limits come from the dataset's real range."""
    body = client.get("/api/dataset/status").json()
    assert body["rows"] == len(sample_df)
    assert body["columns"] == len(sample_df.columns)
    assert body["year_min"] == int(sample_df["year"].min())
    assert body["year_max"] == int(sample_df["year"].max())
    # robust inner bounds sit inside the full range
    assert body["year_min"] <= body["year_p01"] <= body["year_p99"] <= body["year_max"]
    assert body["decade_counts"]
    assert all(int(d) % 10 == 0 for d in body["decade_counts"])


def test_create_run_clamps_years_to_dataset(client):
    """A hand-crafted request cannot ask for a window the dataset lacks."""
    r = client.post("/api/runs", json={"k": 3, "year_from": 1850, "year_to": 2099})
    assert r.status_code == 200
    run_id = r.json()["id"]
    for _ in range(200):
        status = client.get(f"/api/runs/{run_id}").json()
        if status["state"] in ("done", "failed"):
            break
        time.sleep(0.05)
    cfg = client.get(f"/api/runs/{run_id}").json()["config"]
    assert cfg["year_from"] >= 1960
    assert cfg["year_to"] <= 2023


def test_engine_status(client):
    r = client.get("/api/engine")
    assert r.status_code == 200
    assert r.json()["engine"] in ("spark", "pandas")


def test_full_run_lifecycle(client):
    r = client.post("/api/runs", json={"k": 3, "find_best_k": False})
    assert r.status_code == 200
    run_id = r.json()["id"]

    # Poll until done (in-process, should be fast on 400 rows)
    state = None
    status = {}
    for _ in range(300):
        status = client.get(f"/api/runs/{run_id}").json()
        state = status["state"]
        if state in ("done", "failed"):
            break
        time.sleep(0.05)
    assert state == "done", status.get("error")

    results = client.get(f"/api/runs/{run_id}/results").json()
    assert results["rows_clean"] > 0
    assert len(results["clusters"]) == 3
    assert results["decades"]
    # The headline quality metric must never be dropped for large inputs.
    assert results["silhouette"] is not None
    assert results["inertia"] > 0

    # Stage timings recorded, including the whole BDA suite
    status = client.get(f"/api/runs/{run_id}").json()
    done_stages = [s["name"] for s in status["stages"] if s["status"] == "done"]
    assert {"ingest", "clean", "assemble", "kmeans", "pca", "aggregate"} <= set(done_stages)
    assert {"hdfs", "mapreduce", "bloom", "graph", "streaming", "ml", "nosql", "eda"} <= set(
        done_stages
    )


def test_results_include_bda_payload(client):
    run_id = _make_run(client)
    results = client.get(f"/api/runs/{run_id}/results").json()
    bda = results["bda"]
    assert bda["summary"]["analyses_ok"] == 8
    assert bda["hdfs"]["file"]["blocks"] >= 1
    assert bda["mapreduce"]["jobs"]
    assert bda["bloom"]["production"]["false_negatives"] == 0
    assert bda["graph"]["stats"]["nodes"] > 0
    assert bda["ml"]["supervised"]["models"]
    assert bda["nosql"]["commands"]
    assert bda["eda"]["correlation"]
    # the payload must survive a JSON round-trip with no NaN
    assert "NaN" not in json.dumps(results)


def test_concepts_endpoint_lists_every_experiment(client):
    run_id = _make_run(client)
    body = client.get("/api/concepts", params={"run_id": run_id}).json()
    assert body["run_id"] == run_id
    assert body["coverage"]["concepts"] >= 25
    assert body["coverage"]["with_evidence"] == body["coverage"]["concepts"]
    for expected in ("Exp.1", "Exp.2", "Exp.3", "Exp.4", "Exp.5", "Exp.6", "Exp.7", "Exp.8", "CO4"):
        assert expected in body["coverage"]["experiments_covered"]
    for concept in body["concepts"]:
        assert concept["metric"] not in ("", "—")
        assert concept["summary"] and concept["how"]


def test_concepts_marks_the_core_portion(client):
    """The mini-project scope is MapReduce + NoSQL + visualization, marked explicitly."""
    run_id = _make_run(client)
    body = client.get("/api/concepts", params={"run_id": run_id}).json()
    core = [c for c in body["concepts"] if c["primary"]]
    assert core, "expected a core subset"
    assert {c["experiment"] for c in core} == {"Exp.3", "Exp.4", "Exp.5", "Exp.8"}
    assert body["core"]["experiments"] == ["Exp.3", "Exp.4", "Exp.5", "Exp.8"]
    assert body["coverage"]["core_concepts"] == len(core)
    assert body["coverage"]["additional_concepts"] == len(body["concepts"]) - len(core)
    # every experiment reports whether it belongs to the core portion
    core_experiments = {e["id"] for e in body["experiments"] if e["core"]}
    assert core_experiments == {"Exp.3", "Exp.4", "Exp.5", "Exp.8"}


def test_tracks_endpoint_filters(client):
    run_id = _make_run(client)
    r = client.get(f"/api/runs/{run_id}/tracks", params={"page_size": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    assert len(body["tracks"]) <= 10

    decade = body["tracks"][0]["decade"]
    r2 = client.get(f"/api/runs/{run_id}/tracks", params={"decade": decade})
    assert all(t["decade"] == decade for t in r2.json()["tracks"])

    cluster = body["tracks"][0]["cluster"]
    r3 = client.get(f"/api/runs/{run_id}/tracks", params={"cluster": cluster})
    assert all(t["cluster"] == cluster for t in r3.json()["tracks"])

    r4 = client.get(f"/api/runs/{run_id}/tracks", params={"search": "Track 1"})
    assert all("track 1" in t["name"].lower() for t in r4.json()["tracks"])


def test_notebook_export_valid_ipynb(client):
    run_id = _make_run(client)
    r = client.get(f"/api/runs/{run_id}/notebook")
    assert r.status_code == 200
    nb = json.loads(r.content)
    assert nb["nbformat"] == 4
    codes = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert len(codes) >= 16
    all_src = "\n".join("".join(c["source"]) for c in codes)
    assert 'spark.sql.ansi.enabled", "false"' in all_src
    assert 'cast("double").cast("integer")' in all_src
    assert "tracks_features.csv" in all_src
    # the Big Data Analytics sections are exported too
    for needle in (
        "class BloomFilter",
        "def mapreduce(",
        "RandomForestClassifier",
        "label_propagation_communities",
        "linkage(Xh, method=\"ward\")",
        "IsolationForest",
        "runs.aggregate(pipeline)",
        "DATANODES",
    ):
        assert needle in all_src, needle
    md = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "markdown")
    assert "Big Data Analytics findings" in md
    assert "hdfs command transcript" in md


def test_unknown_run_404(client):
    assert client.get("/api/runs/nope").status_code == 404
    assert client.get("/api/runs/nope/results").status_code == 404


def _make_run(client) -> str:
    r = client.post("/api/runs", json={"k": 3})
    run_id = r.json()["id"]
    for _ in range(300):
        status = client.get(f"/api/runs/{run_id}").json()
        if status["state"] in ("done", "failed"):
            assert status["state"] == "done", status.get("error")
            return run_id
        time.sleep(0.05)
    raise AssertionError("run never finished")
