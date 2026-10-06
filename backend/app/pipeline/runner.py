"""Threaded pipeline runner: executes stages, tracks progress, persists results."""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from typing import Any

from ..schemas import StageInfo
from . import tracks as track_store
from .engines import get_engine
from .ingest import load_dataframe

# Core clustering stages, then the Big Data Analytics suite (one stage per
# technique group / lab experiment), then the benchmark that closes the run.
STAGE_ORDER = [
    "ingest",
    "clean",
    "assemble",
    "kmeans",
    "pca",
    "aggregate",
    "benchmark",
    "hdfs",
    "mapreduce",
    "bloom",
    "graph",
    "streaming",
    "ml",
    "nosql",
    "eda",
]


class RunManager:
    """Manages pipeline run lifecycle in-process."""

    def __init__(self, store, backend: str = "unknown"):
        self._store = store
        self.backend = backend
        self._runs: dict[str, dict[str, Any]] = {}

    # ---------------- doc helpers ---------------- #
    def _new_doc(self, run_id: str, engine: str, config: dict) -> dict[str, Any]:
        stages = [StageInfo(name=s).model_dump() for s in STAGE_ORDER]
        return {
            "id": run_id,
            "state": "queued",
            "engine": engine,
            "config": config,
            "stages": stages,
            "current_stage": None,
            "error": None,
            # Stamp it here, not just in the store: stage updates $set the whole
            # in-memory document, so a null created_at would overwrite the stored
            # timestamp on the very first stage transition and break run ordering.
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "finished_at": None,
        }

    @staticmethod
    def _stage_index(doc: dict[str, Any], name: str) -> int:
        for i, s in enumerate(doc["stages"]):
            if s["name"] == name:
                return i
        return -1

    def _set_stage(
        self,
        doc: dict[str, Any],
        name: str,
        status: str,
        seconds: float | None = None,
        detail: str = "",
    ) -> None:
        i = self._stage_index(doc, name)
        if i == -1:
            doc["stages"].append(
                StageInfo(name=name, status=status, seconds=seconds, detail=detail).model_dump()
            )
        else:
            s = doc["stages"][i]
            s["status"] = status
            if seconds is not None:
                s["seconds"] = round(seconds, 3)
            if detail:
                s["detail"] = detail
        self._persist(doc)

    # ---------------- persistence ---------------- #
    def _persist(self, doc: dict[str, Any]) -> None:
        try:
            existing = self._store.get(doc["id"])
            if existing:
                self._store.update(doc["id"], {k: v for k, v in doc.items() if k != "id"})
            else:
                self._store.create(dict(doc))
        except Exception:
            # Store failures must never kill a running pipeline.
            pass

    # ---------------- public API ---------------- #
    def start_run(self, config: dict) -> str:
        run_id = uuid.uuid4().hex[:12]
        engine = get_engine()
        doc = self._new_doc(run_id, engine.name, config)
        doc["state"] = "running"
        doc["current_stage"] = "ingest"
        self._runs[run_id] = doc
        self._persist(doc)
        t = threading.Thread(target=self._execute, args=(run_id, config), daemon=True)
        t.start()
        return run_id

    def get_status(self, run_id: str) -> dict[str, Any] | None:
        doc = self._runs.get(run_id)
        if doc is None:
            doc = self._store.get(run_id)
        return doc

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        live = [d for d in self._runs.values()]
        stored = self._store.list(limit)
        by_id = {d["id"]: d for d in stored}
        for d in live:
            by_id[d["id"]] = d
        return sorted(by_id.values(), key=lambda d: d.get("created_at") or "", reverse=True)[:limit]

    def results_path(self, run_id: str) -> Any:
        return track_store._runs_dir() / run_id / "results.json"

    # ---------------- execution ---------------- #
    def _execute(self, run_id: str, config: dict) -> None:
        doc = self._runs[run_id]
        total_start = time.perf_counter()
        try:
            def progress(msg: str) -> None:
                doc.setdefault("log", []).append(msg)

            # Stage: ingest
            self._set_stage(doc, "ingest", "running")
            df, ingest_seconds, _rows = load_dataframe(progress)
            self._set_stage(doc, "ingest", "done", ingest_seconds, f"{len(df):,} rows")

            # Engine executes clean -> benchmark internally
            self._set_stage(doc, "clean", "running")
            results = engine_run_with_stages(doc, self, df, config, progress)

            finished = time.perf_counter() - total_start
            results["total_seconds"] = round(finished, 2)

            # Persist artifacts BEFORE marking done so pollers never see a
            # "done" run without its tracks/results files.
            track_store.save_tracks(run_id, results.pop("track_frame"))
            results_path = self.results_path(run_id)
            results_path.parent.mkdir(parents=True, exist_ok=True)
            results_path.write_text(json_dumps(results), encoding="utf-8")

            doc["state"] = "done"
            doc["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            doc["results_summary"] = {
                "rows_clean": results["rows_clean"],
                "silhouette": results.get("silhouette"),
                "best_k": results.get("best_k"),
                "total_seconds": results["total_seconds"],
            }
            self._persist(doc)

        except Exception as exc:  # noqa: BLE001
            doc["state"] = "failed"
            doc["error"] = f"{type(exc).__name__}: {exc}"
            doc["traceback"] = traceback.format_exc()
            doc["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._persist(doc)


def engine_run_with_stages(
    doc: dict[str, Any], manager: "RunManager", df, config: dict, progress
):
    """Run the engine, translating its progress messages into stage updates."""
    from ..schemas import RunConfig

    cfg = RunConfig(**config).normalized()
    engine = get_engine()

    stage_map = {
        "[clean]": "clean",
        "[assemble]": "assemble",
        "[kmeans]": "kmeans",
        "[pca]": "pca",
        "[aggregate]": "aggregate",
        "[benchmark]": "benchmark",
    }

    def tracked_progress(msg: str) -> None:
        progress(msg)
        for prefix, stage in stage_map.items():
            if msg.startswith(prefix):
                if doc["current_stage"] != stage:
                    # close previous stage if still running
                    prev = doc["current_stage"]
                    if prev in stage_map.values():
                        manager._set_stage(doc, prev, "done")
                    manager._set_stage(doc, stage, "running")
                    doc["current_stage"] = stage
                break

    manager._set_stage(doc, "clean", "running")
    results = engine.run(df, cfg, progress=tracked_progress)

    # Mark remaining stages done
    for stage in stage_map.values():
        idx = manager._stage_index(doc, stage)
        if idx >= 0 and doc["stages"][idx]["status"] in ("pending", "running"):
            manager._set_stage(doc, stage, "done")

    doc["current_stage"] = None

    # ---- Big Data Analytics suite ---------------------------------------- #
    # Runs after the clustering so every analysis works on labelled data, and it
    # is engine-agnostic: it consumes the same ``track_frame`` the clusterer made.
    results["bda"] = _run_bda(doc, manager, results, cfg, progress)
    return results


def _run_bda(
    doc: dict[str, Any],
    manager: "RunManager",
    results: dict[str, Any],
    cfg,
    progress,
) -> dict[str, Any]:
    """Execute the BDA analyses, mirroring each one into the stage console."""
    from ..bda import STAGE_KEYS, run_bda_analyses
    from .ingest import dataset_path, dataset_profile

    bda_map = {f"[{key}]": key for key in STAGE_KEYS}
    current = {"stage": None}

    def bda_progress(msg: str) -> None:
        progress(msg)
        for prefix, stage in bda_map.items():
            if msg.startswith(prefix):
                if current["stage"] is not None and current["stage"] != stage:
                    manager._set_stage(doc, current["stage"], "done")
                if current["stage"] != stage:
                    manager._set_stage(doc, stage, "running")
                    current["stage"] = stage
                break

    path = dataset_path()
    size_mb = path.stat().st_size / (1024 * 1024) if path.exists() else None
    profile = dataset_profile(path) if path.exists() else {}

    try:
        bda = run_bda_analyses(
            results["track_frame"],
            cfg.features,
            store=getattr(manager, "_store", None),
            store_backend=getattr(manager, "backend", "unknown"),
            run_id=doc["id"],
            k=cfg.k,
            dataset_path=str(path),
            dataset_size_mb=size_mb,
            dataset_rows=profile.get("rows"),
            dataset_columns=profile.get("columns"),
            progress=bda_progress,
        )
    except Exception as exc:  # noqa: BLE001
        bda = {"error": f"{type(exc).__name__}: {exc}", "summary": {"analyses_ok": 0}}
    finally:
        if current["stage"] is not None:
            manager._set_stage(doc, current["stage"], "done")
        current["stage"] = None

    return bda


def json_dumps(obj: Any) -> str:
    """JSON-encode engine/BDA output, coercing numpy scalars and NaN/Inf to null.

    Non-finite floats are not valid JSON, and a single stray NaN deep inside an
    analysis payload would break the whole results file, so they are sanitised
    recursively rather than left to the encoder.
    """
    import json
    import math

    import numpy as np

    def clean(value: Any) -> Any:
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            out = float(value)
            return out if math.isfinite(out) else None
        if isinstance(value, np.ndarray):
            return clean(value.tolist())
        if isinstance(value, dict):
            return {str(k): clean(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [clean(v) for v in value]
        # Compact proxies (pandas/numpy/pyarrow) are stringified so a run can
        # never fail to persist because of an exotic scalar type.
        return str(value)

    return json.dumps(clean(obj))
