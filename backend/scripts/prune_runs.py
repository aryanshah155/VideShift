"""Prune run documents whose artifact directory no longer exists.

Run registry documents and their per-run Parquet/JSON artifacts can drift apart -
most commonly because a test run used a temporary data directory that has since
been cleaned up. Those documents only ever show up as broken links in the UI.

Usage (from ``backend/``)::

    .venv/Scripts/python scripts/prune_runs.py            # dry run, lists only
    .venv/Scripts/python scripts/prune_runs.py --apply    # delete them

Only documents in a terminal state (``done`` / ``failed``) are deleted by
default; anything still ``running`` is reported but left alone unless
``--include-running`` is passed, because an in-flight run has no results yet.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline import tracks as track_store  # noqa: E402
from app.store import open_store, stale_run_docs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually delete the documents")
    parser.add_argument(
        "--include-running",
        action="store_true",
        help="also delete stale documents still marked as running",
    )
    args = parser.parse_args()

    store, backend = open_store()
    artifacts = Path(track_store._runs_dir())
    stale = stale_run_docs(store, artifacts)

    if not stale:
        print(f"[{backend}] no stale run documents - registry and artifacts agree.")
        return 0

    deletable = [d for d in stale if args.include_running or d["state"] != "running"]
    print(f"[{backend}] {len(stale)} stale document(s), {len(deletable)} eligible for deletion:")
    print(f"  artifacts dir: {artifacts}")
    for doc in stale:
        mark = "delete" if doc in deletable else "keep  "
        print(f"  {mark}  {doc['id']}  state={doc['state']:<8} created={doc['created_at']}")

    if not args.apply:
        print("\nDry run - re-run with --apply to delete the eligible documents.")
        return 0

    removed = 0
    for doc in deletable:
        if store.delete(doc["id"]):
            removed += 1
    print(f"\nDeleted {removed} document(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
