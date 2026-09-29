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

    # Stage timings recorded
    status = client.get(f"/api/runs/{run_id}").json()
    done_stages = [s["name"] for s in status["stages"] if s["status"] == "done"]
    assert {"ingest", "clean", "assemble", "kmeans", "pca", "aggregate"} <= set(done_stages)


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
    assert len(codes) >= 8
    all_src = "\n".join("".join(c["source"]) for c in codes)
    assert 'spark.sql.ansi.enabled", "false"' in all_src
    assert 'cast("double").cast("integer")' in all_src
    assert "tracks_features.csv" in all_src


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
