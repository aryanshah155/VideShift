"""Big Data Analytics suite layered on top of the clustering pipeline.

Every analysis maps onto an experiment of the BDA lab manual (CSC702), so the
frontend can present the project as "the lab manual, applied to real data":

    Exp.1  HDFS / Hadoop ecosystem ......... ``hdfs.py``
    Exp.2  ML with PySpark MLlib ........... ``ml_models.py``  (+ pandas engine)
    Exp.3  NoSQL (MongoDB) ................. ``nosql.py``
    Exp.4  MapReduce word count ............ ``mapreduce.py``
    Exp.5  MapReduce aggregates/joins/sort/search ... ``mapreduce.py``
    Exp.6  Bloom filter .................... ``bloom.py``
    Exp.7  Social network analysis ......... ``graph.py``
    Exp.8  Data visualization / statistics . ``eda.py`` + the React dashboards
    CO4    Stream data techniques .......... ``streaming.py``

Each analysis is optional and failure-isolated: a broken analysis degrades to an
``{"error": ...}`` entry instead of killing the run.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from . import bloom, eda, graph, hdfs, mapreduce, ml_models, nosql, streaming

# Stage keys, in the order the runner executes (and the UI shows) them.
STAGE_KEYS = ["hdfs", "mapreduce", "bloom", "graph", "streaming", "ml", "nosql", "eda"]

__all__ = [
    "STAGE_KEYS",
    "run_bda_analyses",
    "bloom",
    "eda",
    "graph",
    "hdfs",
    "mapreduce",
    "ml_models",
    "nosql",
    "streaming",
]


def run_bda_analyses(
    df: Any,
    feature_cols: list[str] | None = None,
    *,
    store: Any = None,
    store_backend: str = "json-fallback",
    run_id: str | None = None,
    k: int = 5,
    dataset_path: str | None = None,
    dataset_size_mb: float | None = None,
    dataset_rows: int | None = None,
    dataset_columns: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run the whole BDA suite over the clustered track frame.

    ``df`` is the engine's ``track_frame``: ``id/name/artists/year/decade/cluster``
    plus the feature columns, i.e. the cleaned + labelled data.
    """
    feature_cols = [c for c in (feature_cols or []) if c in df.columns]

    def emit(stage: str, msg: str) -> None:
        if progress is not None:
            progress(f"[{stage}] {msg}")

    started = time.perf_counter()
    out: dict[str, Any] = {}

    # --- Exp.1: distributed storage layer --------------------------------- #
    try:
        emit("hdfs", "simulating HDFS block placement + fs commands")
        out["hdfs"] = hdfs.simulate_hdfs(
            df,
            path=dataset_path or "tracks_features.csv",
            size_mb=dataset_size_mb,
            file_rows=dataset_rows,
            file_columns=dataset_columns,
        )
        emit("hdfs", f"{out['hdfs']['file']['blocks']} block(s), replication "
                     f"{out['hdfs']['file']['replication']}, "
                     f"{len(out['hdfs']['commands'])} hdfs commands")
    except Exception as exc:  # noqa: BLE001
        out["hdfs"] = {"error": f"{type(exc).__name__}: {exc}"}

    # --- Exp.4 + Exp.5: MapReduce framework ------------------------------- #
    try:
        emit("mapreduce", "running map -> shuffle -> combine -> reduce jobs")
        out["mapreduce"] = mapreduce.run_mapreduce(df, feature_cols)
        jobs = out["mapreduce"]["jobs"]
        pairs = sum(j["stats"]["map_output_pairs"] for j in jobs)
        emit("mapreduce", f"{len(jobs)} jobs, {pairs:,} map output pairs")
    except Exception as exc:  # noqa: BLE001
        out["mapreduce"] = {"error": f"{type(exc).__name__}: {exc}"}

    # --- Exp.6: Bloom filter ---------------------------------------------- #
    try:
        emit("bloom", "building Bloom filter over the artist vocabulary")
        out["bloom"] = bloom.run_bloom(df)
        prod = out["bloom"]["production"]
        emit(
            "bloom",
            f"m={prod['m']:,} bits, k={prod['k']}, "
            f"n={prod['n']:,} items, theoretical FPR {prod['theoretical_fpr']:.4f}",
        )
    except Exception as exc:  # noqa: BLE001
        out["bloom"] = {"error": f"{type(exc).__name__}: {exc}"}

    # --- Exp.7: social network / graph mining ----------------------------- #
    try:
        emit("graph", "building k-NN similarity graph + communities")
        out["graph"] = graph.run_sna(df, feature_cols)
        st = out["graph"]["stats"]
        emit("graph", f"{st['nodes']} nodes, {st['edges']} edges, {st['communities']} communities")
    except Exception as exc:  # noqa: BLE001
        out["graph"] = {"error": f"{type(exc).__name__}: {exc}"}

    # --- CO4: stream windows + concept drift ------------------------------ #
    try:
        emit("streaming", "replaying the corpus as an event-time stream")
        out["streaming"] = streaming.run_streaming(df, feature_cols)
        st = out["streaming"]["stats"]
        emit("streaming", f"{st['batches']} micro-batches, drift points {st['drift_count']}")
    except Exception as exc:  # noqa: BLE001
        out["streaming"] = {"error": f"{type(exc).__name__}: {exc}"}

    # --- Exp.2: supervised ML + model selection --------------------------- #
    try:
        emit("ml", "70/30 split -> RandomForest / DecisionTree / LogisticRegression")
        out["ml"] = ml_models.run_ml(df, feature_cols, k=k)
        sup = out["ml"]["supervised"]
        emit("ml", f"best={sup['best']['name']} accuracy={sup['best']['accuracy']:.3f}")
    except Exception as exc:  # noqa: BLE001
        out["ml"] = {"error": f"{type(exc).__name__}: {exc}"}

    # --- Exp.3: NoSQL console --------------------------------------------- #
    try:
        emit("nosql", "inspecting the MongoDB run collection")
        out["nosql"] = nosql.run_nosql(store, store_backend, run_id=run_id)
        emit("nosql", f"backend={out['nosql']['backend']}, {len(out['nosql']['commands'])} commands")
    except Exception as exc:  # noqa: BLE001
        out["nosql"] = {"error": f"{type(exc).__name__}: {exc}"}

    # --- Exp.8: statistics / EDA ------------------------------------------ #
    try:
        emit("eda", "descriptive stats, correlation matrix, outliers")
        out["eda"] = eda.run_eda(df, feature_cols)
        strongest = out["eda"]["strongest_pairs"][0] if out["eda"]["strongest_pairs"] else None
        if strongest:
            emit("eda", f"strongest |r|: {strongest['a']}~{strongest['b']} r={strongest['r']}")
    except Exception as exc:  # noqa: BLE001
        out["eda"] = {"error": f"{type(exc).__name__}: {exc}"}

    ok = [key for key in STAGE_KEYS if key in out and "error" not in out[key]]
    out["summary"] = {
        "seconds": round(time.perf_counter() - started, 3),
        "analyses_ok": len(ok),
        "analyses_total": len(STAGE_KEYS),
        "available": ok,
        "experiments_covered": [
            "Exp.1 HDFS",
            "Exp.2 MLlib",
            "Exp.3 MongoDB",
            "Exp.4 MapReduce wordcount",
            "Exp.5 MapReduce aggregates/joins/sort/search",
            "Exp.6 Bloom filter",
            "Exp.7 Social network analysis",
            "Exp.8 Visualization",
            "CO4 Stream processing",
        ],
    }
    return out
