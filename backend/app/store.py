"""Persistence layer with MongoDB primary and JSON-file fallback.

Both stores persist the run registry (documents for each run). Results and
track-level data live on disk per-run, so the store only needs to handle
run documents.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonRunStore:
    """File-backed run store used when MongoDB is unavailable."""

    def __init__(self, base_dir: Path):
        self._dir = base_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "runs.json"
        self._lock = threading.Lock()
        if not self._file.exists():
            self._file.write_text("[]", encoding="utf-8")

    def _read(self) -> list[dict[str, Any]]:
        try:
            return json.loads(self._file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write(self, docs: list[dict[str, Any]]) -> None:
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(json.dumps(docs, indent=1), encoding="utf-8")
        tmp.replace(self._file)

    def create(self, doc: dict[str, Any]) -> dict[str, Any]:
        doc = {**doc, "created_at": doc.get("created_at") or _now_iso()}
        with self._lock:
            docs = self._read()
            docs.append(doc)
            self._write(docs)
        return doc

    def update(self, run_id: str, patch: dict[str, Any]) -> None:
        with self._lock:
            docs = self._read()
            for i, d in enumerate(docs):
                if d.get("id") == run_id:
                    docs[i] = {**d, **patch}
                    break
            self._write(docs)

    def get(self, run_id: str) -> dict[str, Any] | None:
        for d in self._read():
            if d.get("id") == run_id:
                return d
        return None

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        return list(reversed(self._read()))[:limit]

    def delete(self, run_id: str) -> bool:
        with self._lock:
            docs = self._read()
            kept = [d for d in docs if d.get("id") != run_id]
            if len(kept) == len(docs):
                return False
            self._write(kept)
        return True


class MongoRunStore:
    """MongoDB-backed run store."""

    def __init__(self, uri: str, db_name: str):
        from pymongo import MongoClient

        self._client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        self._client.admin.command("ping")
        self._col = self._client[db_name]["runs"]

    def create(self, doc: dict[str, Any]) -> dict[str, Any]:
        doc = {**doc, "created_at": doc.get("created_at") or _now_iso()}
        self._col.insert_one(dict(doc))
        return doc

    def update(self, run_id: str, patch: dict[str, Any]) -> None:
        self._col.update_one({"id": run_id}, {"$set": patch})

    def get(self, run_id: str) -> dict[str, Any] | None:
        return self._col.find_one({"id": run_id}, {"_id": 0})

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        cur = self._col.find({}, {"_id": 0}).sort("$natural", -1).limit(limit)
        return list(cur)

    def all_ids(self) -> list[dict[str, Any]]:
        """Minimal projection of every document, for maintenance passes."""
        cur = self._col.find({}, {"_id": 0, "id": 1, "state": 1, "created_at": 1})
        return list(cur)

    def delete(self, run_id: str) -> bool:
        result = self._col.delete_one({"id": run_id})
        return bool(result.deleted_count)


def open_store() -> tuple[Any, str]:
    """Open the best available store. Returns (store, backend_name)."""
    settings = get_settings()
    try:
        store = MongoRunStore(settings.mongo_uri, settings.mongo_db)
        return store, "mongodb"
    except Exception:
        # Fall back inside the configured data dir, so tests that relocate
        # VIBESHIFT_DATA_DIR never read or write the real run registry.
        store = JsonRunStore(settings.data_dir / "_store")
        return store, "json-fallback"


def stale_run_docs(store: Any, artifacts_dir: Path) -> list[dict[str, Any]]:
    """Run documents whose per-run artifact directory is gone.

    These appear when a run registry and its artifacts get separated - the usual
    cause being test runs whose data directory was a temporary folder, or a run
    deleted from disk. They only ever render as broken links in the UI.
    """
    rows: list[dict[str, Any]] = []
    listed = (
        store.all_ids()
        if hasattr(store, "all_ids")
        else [
            {"id": d.get("id"), "state": d.get("state"), "created_at": d.get("created_at")}
            for d in store.list(10_000)
        ]
    )
    for doc in listed:
        run_id = doc.get("id")
        if not run_id:
            continue
        if not (artifacts_dir / run_id / "results.json").exists():
            rows.append(
                {
                    "id": run_id,
                    "state": doc.get("state"),
                    "created_at": doc.get("created_at"),
                }
            )
    return rows
