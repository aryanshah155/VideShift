"""Concept registry endpoint: the lab-manual mapping, annotated with live evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from ..bda.catalog import CORE, CONCEPTS, EXPERIMENTS, _get
from ..pipeline import tracks as track_store

router = APIRouter()


def _results_path(run_id: str) -> Path:
    return Path(track_store._runs_dir()) / run_id / "results.json"


def _latest_done_run(request: Request) -> str | None:
    manager = request.app.state.run_manager
    for doc in manager.list_runs(50):
        if doc.get("state") == "done" and _results_path(doc["id"]).exists():
            return doc["id"]
    return None


def _load_results(run_id: str) -> dict[str, Any] | None:
    path = _results_path(run_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def concepts_payload(request: Request, run_id: str | None = None) -> dict[str, Any]:
    """Return the concept registry with a live metric for each technique."""
    rid = run_id or _latest_done_run(request)
    results = _load_results(rid) if rid else None
    bda = (results or {}).get("bda") or {}

    rows: list[dict[str, Any]] = []
    with_evidence = 0
    for concept in CONCEPTS:
        metric = "—"
        # A concept counts as evidenced only if its payload path actually exists;
        # runs recorded before the BDA suite existed have no `bda` block at all.
        # Evidence paths are written as "bda.<path>" or "results.<path>".
        evidence_path = concept["evidence"]
        if evidence_path.startswith("results."):
            root, path = results or {}, evidence_path[len("results.") :]
        elif evidence_path.startswith("bda."):
            root, path = bda, evidence_path[len("bda.") :]
        else:
            root, path = bda, evidence_path
        has_evidence = _get(root, path) not in (None, {}, [])
        if results and has_evidence:
            try:
                metric = concept["metric"](bda, results)
            except Exception as exc:  # noqa: BLE001
                metric = f"n/a ({type(exc).__name__})"
                has_evidence = False
        if has_evidence:
            with_evidence += 1
        rows.append(
            {
                "id": concept["id"],
                "name": concept["name"],
                "experiment": concept["experiment"],
                "co_lo": concept["co_lo"],
                "category": concept["category"],
                "summary": concept["summary"],
                "how": concept["how"],
                "evidence": concept["evidence"],
                "metric": metric,
                "has_evidence": has_evidence,
                "primary": bool(concept.get("primary")),
            }
        )

    categories: dict[str, int] = {}
    for row in rows:
        categories[row["category"]] = categories.get(row["category"], 0) + 1

    experiments_covered = sorted({row["experiment"] for row in rows})
    core_rows = [r for r in rows if r["primary"]]
    core_with_evidence = sum(1 for r in core_rows if r["has_evidence"])

    return {
        "run_id": rid,
        "has_run": bool(results),
        "core": CORE,
        "experiments": EXPERIMENTS,
        "concepts": rows,
        "categories": [
            {"category": k, "count": v}
            for k, v in sorted(categories.items(), key=lambda kv: -kv[1])
        ],
        "coverage": {
            "concepts": len(rows),
            "with_evidence": with_evidence,
            "experiments": len(experiments_covered),
            "experiments_covered": experiments_covered,
            "core_concepts": len(core_rows),
            "core_with_evidence": core_with_evidence,
            "additional_concepts": len(rows) - len(core_rows),
            "analyses_ok": (bda.get("summary") or {}).get("analyses_ok"),
            "analyses_total": (bda.get("summary") or {}).get("analyses_total"),
            "bda_seconds": (bda.get("summary") or {}).get("seconds"),
        },
        "summary": bda.get("summary"),
    }
