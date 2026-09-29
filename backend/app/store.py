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


def open_store() -> tuple[Any, str]:
    """Open the best available store. Returns (store, backend_name)."""
    settings = get_settings()
    try:
        store = MongoRunStore(settings.mongo_uri, settings.mongo_db)
        return store, "mongodb"
    except Exception:
        base = Path(__file__).resolve().parent.parent / "data" / "_store"
        store = JsonRunStore(base)
        return store, "json-fallback"
