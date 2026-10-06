"""NoSQL console (Exp.3, CO3-LO3).

The manual installs MongoDB and runs "minimum 20 commands" against a
schemaless collection. VibeShift persists every run document to MongoDB (with a
JSON-file fallback), so this module reports the *real* collection state and the
same command transcript, with live results where a connection exists.

Everything here is strictly read-only: ``updateOne`` / ``deleteOne`` / drop
commands are printed with their purpose but never executed, so the lab console
can never damage the run history.
"""

from __future__ import annotations

import json
import time
from typing import Any

EXPERIMENT = "Exp.3 / CO3-LO3"
TITLE = "NoSQL with MongoDB: schemaless documents, queries, aggregation pipeline"


def _flatten(doc: dict[str, Any], prefix: str = "", limit: int = 40) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(doc, dict):
        return rows
    for key, value in doc.items():
        if len(rows) >= limit:
            break
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            rows.extend(_flatten(value, path + ".", limit - len(rows)))
        elif isinstance(value, list):
            rows.append(
                {
                    "path": path,
                    "type": f"array[{len(value)}]",
                    "sample": str(value[:2])[:70],
                }
            )
        else:
            rows.append(
                {"path": path, "type": type(value).__name__, "sample": str(value)[:70]}
            )
    return rows


def run_nosql(
    store: Any,
    store_backend: str,
    *,
    run_id: str | None = None,
    db_name: str = "vibeshift",
    collection: str = "runs",
) -> dict[str, Any]:
    t0 = time.perf_counter()
    is_mongo = hasattr(store, "_col")
    base: dict[str, Any] = {
        "experiment": EXPERIMENT,
        "title": TITLE,
        "backend": store_backend,
        "database": db_name,
        "collection": collection,
        "connected": bool(is_mongo),
        "run_document_id": run_id,
        "read_only": True,
    }

    if not is_mongo:
        # JSON fallback: still show the command surface and the local file state.
        docs: list[dict[str, Any]] = []
        try:
            docs = store.list(50) if store is not None else []
        except Exception:
            docs = []
        base.update(
            {
                "stats": {
                    "documents": len(docs),
                    "avg_obj_size": None,
                    "storage_bytes": None,
                    "indexes": [],
                    "note": "MongoDB unreachable - runs are persisted to a JSON file instead.",
                },
                "schema": _flatten(docs[0]) if docs else [],
                "sample_document": json.dumps(docs[0], indent=1)[:1200] if docs else "",
                "queries": [
                    {
                        "filter": '{ "state": "done" }',
                        "desc": "Runs that finished successfully",
                        "result": "n/a (json-fallback)",
                    }
                ],
                "commands": _commands(None, None, {}),
                "seconds": round(time.perf_counter() - t0, 3),
            }
        )
        return base

    col = store._col
    db = col.database

    def _count(spec: dict[str, Any]) -> Any:
        try:
            return int(col.count_documents(spec))
        except Exception:
            return None

    live: dict[str, Any] = {
        "documents": _count({}),
        "done": _count({"state": "done"}),
        "running": _count({"state": "running"}),
        "failed": _count({"state": "failed"}),
        "k5": _count({"config.k": 5}),
        "energy_feature": _count({"config.features": "energy"}),
        "before_2000": _count({"config.year_from": {"$lt": 2000}}),
        "silhouette_gt_zero": _count({"results_summary.silhouette": {"$gt": 0}}),
    }
    try:
        live["engines"] = [str(e) for e in col.distinct("engine")]
    except Exception:
        live["engines"] = []
    try:
        live["by_state"] = [
            {"state": str(row.get("_id")), "count": int(row.get("n", 0))}
            for row in col.aggregate(
                [{"$group": {"_id": "$state", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}]
            )
        ]
    except Exception:
        live["by_state"] = []
    try:
        stats = db.command("collStats", collection)
        live["avg_obj_size"] = stats.get("avgObjSize")
        live["storage_bytes"] = stats.get("storageSize")
        live["size_bytes"] = stats.get("size")
        live["index_count"] = stats.get("nindexes")
    except Exception:
        live["avg_obj_size"] = None

    try:
        sample = col.find_one({"id": run_id}, {"_id": 0}) if run_id else None
        if sample is None:
            sample = col.find_one({}, {"_id": 0})
    except Exception:
        sample = None

    sample_doc = sample or {}
    recent: list[dict[str, Any]] = []
    try:
        recent = list(
            col.find(
                {},
                {"_id": 0, "id": 1, "state": 1, "engine": 1, "config.k": 1},
            )
            .sort("$natural", -1)
            .limit(6)
        )
    except Exception:
        recent = []

    indexes: list[dict[str, Any]] = []
    try:
        for name, spec in col.index_information().items():
            indexes.append({"name": name, "keys": str(spec.get("key"))})
    except Exception:
        indexes = []

    base.update(
        {
            "stats": {
                "documents": live["documents"],
                "avg_obj_size": live["avg_obj_size"],
                "storage_bytes": live["storage_bytes"],
                "size_bytes": live.get("size_bytes"),
                "index_count": live.get("index_count"),
                "indexes": indexes,
                "done": live["done"],
                "running": live["running"],
                "failed": live["failed"],
                "engines": live["engines"],
                "by_state": live["by_state"],
                "note": "Live MongoDB collection statistics.",
            },
            "schema": _flatten(sample_doc),
            "sample_document": json.dumps(sample_doc, indent=1, default=str)[:1600],
            "recent_documents": recent,
            "queries": [
                {
                    "filter": '{ "state": "done" }',
                    "desc": "Runs that finished successfully",
                    "result": str(live["done"]),
                },
                {
                    "filter": '{ "state": "failed" }',
                    "desc": "Runs that raised an error",
                    "result": str(live["failed"]),
                },
                {
                    "filter": '{ "config.k": 5 }',
                    "desc": "Runs configured with 5 clusters (nested-field equality)",
                    "result": str(live["k5"]),
                },
                {
                    "filter": '{ "config.year_from": { "$lt": 2000 } }',
                    "desc": "The manual's 'year field less than' query, on a nested field",
                    "result": str(live["before_2000"]),
                },
                {
                    "filter": '{ "config.features": "energy" }',
                    "desc": "Array-contains match on the feature list",
                    "result": str(live["energy_feature"]),
                },
                {
                    "filter": '{ "results_summary.silhouette": { "$gt": 0 } }',
                    "desc": "Runs with a positive silhouette score",
                    "result": str(live["silhouette_gt_zero"]),
                },
                {
                    "filter": 'db.runs.aggregate([{$group:{_id:"$state", n:{$sum:1}}}])',
                    "desc": "Aggregation pipeline grouping documents by state",
                    "result": ", ".join(
                        f"{r['state']}={r['count']}" for r in live["by_state"]
                    )
                    or "—",
                },
                {
                    "filter": 'db.runs.distinct("engine")',
                    "desc": "Distinct engines used across the run history",
                    "result": ", ".join(live["engines"]) or "—",
                },
            ],
            "commands": _commands(col, db, live),
            "seconds": round(time.perf_counter() - t0, 3),
        }
    )
    base["concepts"] = [
        "document model / schemaless collections",
        "CRUD operations (insertOne, find, updateOne, deleteOne)",
        "nested-field and array queries",
        "comparison operators ($lt, $gt) and projections",
        "aggregation pipeline ($group, $sum, $sort)",
        "indexes and collection statistics",
        "unstructured persistence alongside Parquet artifacts",
    ]
    return base


def _commands(col: Any, db: Any, live: dict[str, Any]) -> list[dict[str, Any]]:
    """The manual's 20+ command list, with live results where available."""

    def run(fn, fallback: str = "—"):
        if col is None:
            return fallback
        try:
            value = fn()
            return str(value)
        except Exception as exc:  # noqa: BLE001
            return f"error: {type(exc).__name__}"

    mongosh = "mongosh"
    return [
        {"cmd": "show dbs", "purpose": "List the databases on the server", "result": run(lambda: ", ".join(db.client.list_database_names()))},
        {"cmd": "use vibeshift", "purpose": "Select (or implicitly create) the database", "result": "switched to db vibeshift"},
        {"cmd": "db.getName()", "purpose": "Confirm the currently selected database", "result": run(lambda: db.name)},
        {"cmd": "show collections", "purpose": "List collections in the selected database", "result": run(lambda: ", ".join(db.list_collection_names()))},
        {"cmd": "db.stats()", "purpose": "Storage and object statistics for the database", "result": run(lambda: f"collections={db.command('dbStats')['collections']}, dataSize={db.command('dbStats')['dataSize']}B")},
        {"cmd": "db.runs.stats()", "purpose": "Collection statistics (count, avg object size, indexes)", "result": run(lambda: f"count={db.command('collStats', 'runs')['count']}, avgObjSize={db.command('collStats', 'runs')['avgObjSize']}B, indexes={db.command('collStats', 'runs')['nindexes']}")},
        {"cmd": 'db.runs.insertOne({ id: "...", state: "done" })', "purpose": "Create one run document (done automatically by the pipeline)", "result": f"{live.get('documents', 0)} documents exist (inserted by the API, not this console)"},
        {"cmd": 'db.runs.insertMany([...])', "purpose": "Bulk insert", "result": "used internally when the runner persists stage updates"},
        {"cmd": "db.runs.countDocuments({})", "purpose": "Count all documents", "result": str(live.get("documents", "—"))},
        {"cmd": 'db.runs.find({ state: "done" }).count()', "purpose": "Count completed runs", "result": str(live.get("done", "—"))},
        {"cmd": "db.runs.find()", "purpose": "Read all documents (cursor)", "result": run(lambda: col.find_one({}, {"_id": 0, "id": 1}) or "empty")},
        {"cmd": "db.runs.find().pretty()", "purpose": "Read data from the collection, formatted", "result": "see sample document panel"},
        {"cmd": "db.runs.findOne()", "purpose": "Return a single document", "result": run(lambda: (col.find_one({}, {"_id": 0, "id": 1}) or {}).get("id", "empty"))},
        {"cmd": 'db.runs.find({ "config.k": 5 })', "purpose": "Query on a nested field (dotted path)", "result": str(live.get("k5", "—"))},
        {"cmd": 'db.runs.find({ "config.year_from": { $lt: 2000 } })', "purpose": "Comparison operator $lt (the manual's 'year less than' query)", "result": str(live.get("before_2000", "—"))},
        {"cmd": 'db.runs.find({ "config.features": "energy" })', "purpose": "Array-contains equality query", "result": str(live.get("energy_feature", "—"))},
        {"cmd": 'db.runs.find({}, { id: 1, state: 1, _id: 0 })', "purpose": "Projection: return only the named fields", "result": run(lambda: col.count_documents({}))},
        {"cmd": "db.runs.distinct(\"engine\")", "purpose": "Distinct values of a field", "result": ", ".join(live.get("engines", [])) or "—"},
        {"cmd": 'db.runs.aggregate([{ $group: { _id: "$state", n: { $sum: 1 } } }])', "purpose": "Aggregation pipeline grouping by state", "result": ", ".join(f"{r['state']}={r['count']}" for r in live.get("by_state", [])) or "—"},
        {"cmd": 'db.runs.aggregate([{ $match: { state: "done" } }, { $sort: { createdAt: -1 } }])', "purpose": "$match + $sort pipeline stages", "result": run(lambda: col.count_documents({"state": "done"}))},
        {"cmd": 'db.runs.updateOne({ id: "..." }, { $set: { state: "done" } })', "purpose": "Update a field on one document", "result": "executed by the runner on every stage transition (not from this console)"},
        {"cmd": 'db.runs.deleteOne({ id: "..." })', "purpose": "Remove one document", "result": "not executed — read-only lab console"},
        {"cmd": "db.runs.createIndex({ id: 1 })", "purpose": "Index for fast lookups by run id", "result": run(lambda: ", ".join(col.index_information().keys()))},
        {"cmd": "db.runs.drop()", "purpose": "Drop the whole collection", "result": "not executed — read-only lab console"},
        {"cmd": "db.dropDatabase()", "purpose": "Drop the selected database", "result": "not executed — read-only lab console"},
        {"cmd": "exit", "purpose": "Close the mongosh session", "result": f"({mongosh} session ends)"},
    ]
