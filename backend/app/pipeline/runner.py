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

STAGE_ORDER = [
    "ingest",
    "clean",
    "assemble",
    "kmeans",
    "pca",
    "aggregate",
    "benchmark",
]


class RunManager:
    """Manages pipeline run lifecycle in-process."""

    def __init__(self, store):
        self._store = store
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
            "created_at": None,
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
    return results


def json_dumps(obj: Any) -> str:
    import json

    def default(o):
        import numpy as np

        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)

    return json.dumps(obj, default=default)
