"""Concept registry: every Big Data Analytics technique used, mapped to the lab manual.

This is the single source of truth behind the frontend's "BDA Concepts" page. For
each technique it records:

* the manual experiment / course outcome it satisfies,
* a short explanation of the technique and how this project uses it,
* the JSON path inside a run's ``bda`` payload where the evidence lives, and
* a ``metric`` callable that extracts the live number to display.

Keeping the mapping in one place means the UI can never drift from what the
pipeline actually did.
"""

from __future__ import annotations

from typing import Any, Callable

MetricFn = Callable[[dict[str, Any], dict[str, Any]], str]


def _get(data: Any, path: str, default: Any = None) -> Any:
    """Dotted-path lookup that tolerates missing intermediate keys."""
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict):
            if part not in cur:
                return default
            cur = cur[part]
        elif isinstance(cur, list):
            if not part.isdigit() or int(part) >= len(cur):
                return default
            cur = cur[int(part)]
        else:
            return default
    return cur


def _num(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):,.{digits}f}{suffix}"
    except Exception:
        return str(value)


def _int(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)


def _m_hdfs(bda: dict, results: dict) -> str:
    f = _get(bda, "hdfs.file", {})
    return f"{_int(f.get('blocks'))} block(s) · repl {f.get('replication')} · {f.get('stored_human', '—')} on disk"


def _m_hdfs_cmds(bda: dict, results: dict) -> str:
    return f"{len(_get(bda, 'hdfs.commands', []) or [])} hdfs commands"


def _m_mr_wordcount(bda: dict, results: dict) -> str:
    top = _get(bda, "mapreduce.jobs.0.output.0", {})
    if not top:
        return "—"
    return f"top token '{top.get('key')}' × {_int(top.get('value'))}"


def _m_mr_pairs(bda: dict, results: dict) -> str:
    jobs = _get(bda, "mapreduce.jobs", []) or []
    pairs = sum(int(_get(j, "stats.map_output_pairs", 0) or 0) for j in jobs)
    return f"{_int(pairs)} map output pairs · {len(jobs)} jobs"


def _m_mr_combiner(bda: dict, results: dict) -> str:
    saved = _get(bda, "mapreduce.jobs.1.stats.combine_saved_pct")
    return f"combiner cut shuffle traffic by {_num(saved, 1, '%')}"


def _m_mr_join(bda: dict, results: dict) -> str:
    out = _get(bda, "mapreduce.jobs.2.output", []) or []
    return f"{len(out)} joined groups"


def _m_mr_topn(bda: dict, results: dict) -> str:
    top = _get(bda, "mapreduce.jobs.3.output.0", {})
    return f"top artist '{top.get('key', '—')}' ({_int(top.get('value'))} tracks)" if top else "—"


def _m_mr_index(bda: dict, results: dict) -> str:
    st = _get(bda, "mapreduce.jobs.4.stats", {}) or {}
    return f"{_int(st.get('reduce_groups'))} distinct tokens indexed"


def _m_bloom(bda: dict, results: dict) -> str:
    p = _get(bda, "bloom.production", {}) or {}
    return (
        f"m={_int(p.get('m'))} bits, k={p.get('k')}, FPR {p.get('theoretical_fpr')} "
        f"({p.get('memory_kb')} KB)"
    )


def _m_bloom_lab(bda: dict, results: dict) -> str:
    lab = _get(bda, "bloom.lab_exercise", {}) or {}
    return (
        f"{lab.get('bits')} bits · {lab.get('bits_set')} set · "
        f"{lab.get('true_positives')} TP / {lab.get('false_positives')} FP"
    )


def _m_kmeans(bda: dict, results: dict) -> str:
    k = results.get("best_k") or _get(results, "config.k")
    return f"k={k} · silhouette {_num(results.get('silhouette'), 3)} · inertia {_int(results.get('inertia'))}"


def _m_pca(bda: dict, results: dict) -> str:
    return f"{len(results.get('pca_sample', []))} points projected to 2 components"


def _m_scaler(bda: dict, results: dict) -> str:
    feats = _get(results, "config.features", []) or []
    return f"{len(feats)} features standardized (mean 0, std 1, ddof=0)"


def _m_split(bda: dict, results: dict) -> str:
    sp = _get(bda, "ml.supervised.split", {}) or {}
    return f"{_int(sp.get('train_rows'))} train / {_int(sp.get('test_rows'))} test (70/30, seed 42)"


def _m_supervised(bda: dict, results: dict) -> str:
    best = _get(bda, "ml.supervised.best", {}) or {}
    if not best:
        return "—"
    return f"{best.get('name')} · accuracy {_num(best.get('accuracy'), 3)} · F1 {_num(best.get('f1'), 3)}"


def _m_metrics(bda: dict, results: dict) -> str:
    models = _get(bda, "ml.supervised.models", []) or []
    return f"{len(models)} models scored on accuracy/precision/recall/F1/ROC-AUC"


def _m_importance(bda: dict, results: dict) -> str:
    imp = _get(bda, "ml.supervised.feature_importance", {}) or {}
    if not imp:
        return "—"
    top = list(imp.items())[0]
    return f"top driver: {top[0]} ({top[1]})"


def _m_hier(bda: dict, results: dict) -> str:
    h = _get(bda, "ml.hierarchical", {}) or {}
    if "error" in h:
        return "—"
    return f"{h.get('rows_used')} leaves · max merge height {h.get('max_height')} · ARI {h.get('ari_vs_agglomerative_cut')}"


def _m_elbow(bda: dict, results: dict) -> str:
    e = _get(bda, "ml.elbow", {}) or {}
    return f"elbow at k={e.get('elbow_k')} over k={e.get('k', [])[:1]}..{e.get('k', [])[-1:]}"


def _m_mongo(bda: dict, results: dict) -> str:
    n = _get(bda, "nosql.stats.documents")
    return f"{_int(n)} run documents in {_get(bda, 'nosql.database')}.{_get(bda, 'nosql.collection')}"


def _m_mongo_cmds(bda: dict, results: dict) -> str:
    return f"{len(_get(bda, 'nosql.commands', []) or [])} NoSQL commands documented"


def _m_sna(bda: dict, results: dict) -> str:
    s = _get(bda, "graph.stats", {}) or {}
    return f"{_int(s.get('nodes'))} nodes · {_int(s.get('edges'))} edges · density {s.get('density')}"


def _m_communities(bda: dict, results: dict) -> str:
    s = _get(bda, "graph.stats", {}) or {}
    return f"{s.get('communities')} communities · modularity {s.get('modularity')} · {s.get('components')} component(s)"


def _m_degree(bda: dict, results: dict) -> str:
    s = _get(bda, "graph.stats", {}) or {}
    return (
        f"avg degree {s.get('avg_degree')} · max {s.get('max_degree')} · "
        f"clustering coeff {s.get('avg_clustering_coefficient')}"
    )


def _m_stream(bda: dict, results: dict) -> str:
    s = _get(bda, "streaming.stats", {}) or {}
    return f"{s.get('batches')} micro-batches of {_int(s.get('batch_size'))}, window {s.get('window')}"


def _m_late(bda: dict, results: dict) -> str:
    s = _get(bda, "streaming.stats", {}) or {}
    return f"{_int(s.get('late_events'))} late events ({s.get('late_pct')}%) vs watermark"


def _m_drift(bda: dict, results: dict) -> str:
    s = _get(bda, "streaming.stats", {}) or {}
    return f"{s.get('drift_count')} drift points at |z| > {s.get('drift_z_threshold')}"


def _m_corr(bda: dict, results: dict) -> str:
    pairs = _get(bda, "eda.strongest_pairs", []) or []
    if not pairs:
        return "—"
    p = pairs[0]
    return f"strongest pair {p['a']}~{p['b']} r={p['r']}"


def _m_outliers(bda: dict, results: dict) -> str:
    n = _get(bda, "eda.outlier_flags_total")
    a = _get(bda, "eda.anomaly.count")
    return f"{_int(n)} IQR flags · {_int(a)} IsolationForest anomalies"


def _m_viz(bda: dict, results: dict) -> str:
    decades = len(results.get("decades", []))
    clusters = len(results.get("clusters", []))
    return f"{decades}×{clusters} heatmap + PCA scatter + trend lines"


def _m_bench(bda: dict, results: dict) -> str:
    b = results.get("benchmark") or {}
    return f"{b.get('label_a')} vs {b.get('label_b')} → {b.get('speedup')}× speedup"


# The portion selected for the mini-project: MapReduce (Exp.4/Exp.5), NoSQL
# persistence (Exp.3) and data visualization (Exp.8). Everything else is still
# implemented and still runs - it is simply presented as additional analysis.
CORE_EXPERIMENTS: list[str] = ["Exp.3", "Exp.4", "Exp.5", "Exp.8"]

CORE = {
    "title": "MapReduce · NoSQL persistence · Data visualization",
    "experiments": CORE_EXPERIMENTS,
    "why": (
        "These three carry the project: MapReduce shows the distributed processing "
        "model on real records (word count, aggregates, joins, sorting, searching), "
        "MongoDB shows NoSQL persistence of schemaless run documents, and the "
        "visualization layer turns both into the decade x cluster dashboards."
    ),
}


CONCEPTS: list[dict[str, Any]] = [
    # ---------------- Exp.1 ---------------- #
    {
        "id": "hdfs-blocks",
        "name": "HDFS blocks, replication & rack awareness",
        "experiment": "Exp.1",
        "co_lo": "CO1 / LO1",
        "category": "Distributed storage",
        "summary": "HDFS splits a file into fixed-size blocks, replicates each block 3× and places replicas rack-aware across DataNodes.",
        "how": "The corpus is modelled as one HDFS file against a 4-node / 2-rack cluster, with the block map, replica locations and DataNode occupancy computed from the real file size.",
        "evidence": "bda.hdfs",
        "metric": _m_hdfs,
    },
    {
        "id": "hdfs-commands",
        "name": "hdfs dfs / dfsadmin command surface",
        "experiment": "Exp.1",
        "co_lo": "CO1 / LO1",
        "category": "Distributed storage",
        "summary": "mkdir, put, ls, count, du, cat, stat, fsck, setrep, balancer, expunge, report, safemode.",
        "how": "A 24-command transcript is rendered with the dataset's real byte counts, block ids, replica racks and fsck health output.",
        "evidence": "bda.hdfs.commands",
        "metric": _m_hdfs_cmds,
    },
    # ---------------- Exp.4 + Exp.5 ---------------- #
    {
        "id": "mapreduce-wordcount",
        "name": "MapReduce word count",
        "experiment": "Exp.4",
        "co_lo": "CO2 / LO2",
        "category": "Distributed processing",
        "summary": "map emits (word, 1); a combiner sums locally; the reducer produces final counts.",
        "how": "Track titles are tokenized (stopword-filtered) and counted by the in-process MapReduce runtime.",
        "evidence": "bda.mapreduce.jobs.0",
        "metric": _m_mr_wordcount,
    },
    {
        "id": "mapreduce-phases",
        "name": "Map / shuffle / combine / reduce phases",
        "experiment": "Exp.4",
        "co_lo": "CO2 / LO2",
        "category": "Distributed processing",
        "summary": "Every phase is separately timed and counted: map tasks, key partitioning, shuffle groups and reducers.",
        "how": "The runtime exposes partition_pair counts per reducer plus per-phase timings for five different jobs.",
        "evidence": "bda.mapreduce.jobs",
        "metric": _m_mr_pairs,
    },
    {
        "id": "mapreduce-combiner",
        "name": "Combiners cutting shuffle traffic",
        "experiment": "Exp.5",
        "co_lo": "CO2 / LO2",
        "category": "Distributed processing",
        "summary": "A combiner aggregates map output per map task so fewer pairs cross the network.",
        "how": "The aggregates job reports pairs before/after the combiner and the resulting percentage saved.",
        "evidence": "bda.mapreduce.jobs.1.stats",
        "metric": _m_mr_combiner,
    },
    {
        "id": "mapreduce-join",
        "name": "Map-side (broadcast) join",
        "experiment": "Exp.5",
        "co_lo": "CO2 / LO2",
        "category": "Distributed processing",
        "summary": "Joining a large relation with a small one by broadcasting the small table to every map task.",
        "how": "Tracks are enriched with their cluster label (inner-join semantics) with no shuffle of the large side.",
        "evidence": "bda.mapreduce.jobs.2",
        "metric": _m_mr_join,
    },
    {
        "id": "mapreduce-topn",
        "name": "Sorting & top-N",
        "experiment": "Exp.5",
        "co_lo": "CO2 / LO2",
        "category": "Distributed processing",
        "summary": "Count per key, then sort the reduced output and cut the top N.",
        "how": "Artist frequency across the corpus, sorted descending after the reduce phase.",
        "evidence": "bda.mapreduce.jobs.3",
        "metric": _m_mr_topn,
    },
    {
        "id": "mapreduce-inverted-index",
        "name": "Searching via an inverted index",
        "experiment": "Exp.5",
        "co_lo": "CO2 / LO2",
        "category": "Distributed processing",
        "summary": "token → posting list, so a query is a lookup instead of a full scan.",
        "how": "Title tokens are mapped to track ids with a bounded posting cap, then a term is queried.",
        "evidence": "bda.mapreduce.jobs.4",
        "metric": _m_mr_index,
    },
    # ---------------- Exp.6 ---------------- #
    {
        "id": "bloom-production",
        "name": "Bloom filter sized for a 1% false-positive rate",
        "experiment": "Exp.6",
        "co_lo": "CO4 / LO4",
        "category": "Probabilistic data structures",
        "summary": "A bit array plus k hash functions test membership in O(k) with no false negatives.",
        "how": "Artist names are indexed; m and k are derived from the item count with m = -n ln p / (ln 2)² and double hashing.",
        "evidence": "bda.bloom.production",
        "metric": _m_bloom,
    },
    {
        "id": "bloom-lab-table",
        "name": "Bloom filter lab table (ASCII → hashes → bits)",
        "experiment": "Exp.6",
        "co_lo": "CO4 / LO4",
        "category": "Probabilistic data structures",
        "summary": "Insert words, set bits, then classify test words as True positive / False positive / Not present.",
        "how": "The manual's exercise is executed literally, including a 11-bit variant that saturates to show why sizing matters.",
        "evidence": "bda.bloom.lab_exercise",
        "metric": _m_bloom_lab,
    },
    # ---------------- Exp.2 ---------------- #
    {
        "id": "ml-kmeans",
        "name": "Distributed K-Means (MLlib semantics)",
        "experiment": "Exp.2",
        "co_lo": "CO2 / LO2",
        "category": "Machine learning",
        "summary": "K-Means with seed 42 over the scaled feature vectors, evaluated by silhouette and inertia/training cost.",
        "how": "Runs on PySpark MLlib when a compatible JVM/Python is present, otherwise the pandas/sklearn mirror.",
        "evidence": "results.clusters",
        "metric": _m_kmeans,
    },
    {
        "id": "ml-pca",
        "name": "PCA dimensionality reduction (8D → 2D)",
        "experiment": "Exp.2",
        "co_lo": "CO2 / LO2",
        "category": "Machine learning",
        "summary": "Principal component analysis projects the scaled feature space to two components for visualization.",
        "how": "The projection is plotted as an interactive scatter with points coloured by cluster.",
        "evidence": "results.pca_sample",
        "metric": _m_pca,
    },
    {
        "id": "ml-standardscaler",
        "name": "VectorAssembler + StandardScaler",
        "experiment": "Exp.2",
        "co_lo": "CO2 / LO2",
        "category": "Machine learning",
        "summary": "Features are assembled into one vector and standardized so tempo/loudness ranges don't dominate distance.",
        "how": "numpy standardization with ddof=0 reproduces Spark's StandardScaler(withMean, withStd) exactly.",
        "evidence": "results.config_used.features",
        "metric": _m_scaler,
    },
    {
        "id": "ml-split",
        "name": "70/30 train–test split",
        "experiment": "Exp.2",
        "co_lo": "CO2 / LO2",
        "category": "Machine learning",
        "summary": "randomSplit([0.7, 0.3], seed=42) — hold out test data before evaluating.",
        "how": "train_test_split(test_size=0.3, random_state=42) on the era-classification target.",
        "evidence": "bda.ml.supervised.split",
        "metric": _m_split,
    },
    {
        "id": "ml-supervised",
        "name": "Supervised classification: RF / DecisionTree / LogisticRegression",
        "experiment": "Exp.2",
        "co_lo": "CO2 / LO2",
        "category": "Machine learning",
        "summary": "Predict whether a track is modern (year ≥ 2000) from its acoustic features alone.",
        "how": "Three classifiers are trained and ranked on the held-out test set.",
        "evidence": "bda.ml.supervised.models",
        "metric": _m_supervised,
    },
    {
        "id": "ml-metrics",
        "name": "Accuracy, precision, recall, F1, ROC-AUC",
        "experiment": "Exp.2",
        "co_lo": "CO2 / LO2",
        "category": "Machine learning",
        "summary": "The metric set the manual lists for classification, plus the ROC curve.",
        "how": "Each model is scored on the 30% holdout and its ROC curve is plotted.",
        "evidence": "bda.ml.supervised.models",
        "metric": _m_metrics,
    },
    {
        "id": "ml-confusion",
        "name": "Confusion matrix",
        "experiment": "Exp.2",
        "co_lo": "CO2 / LO2",
        "category": "Machine learning",
        "summary": "TP/FP/FN/TN breakdown of the best classifier on the test split.",
        "how": "Rendered as a 2×2 grid on the results page.",
        "evidence": "bda.ml.supervised.confusion_matrix",
        "metric": lambda bda, r: f"CM {_get(bda, 'ml.supervised.confusion_matrix')}",
    },
    {
        "id": "ml-importance",
        "name": "Feature importance",
        "experiment": "Exp.2",
        "co_lo": "CO2 / LO2",
        "category": "Machine learning",
        "summary": "Random-Forest impurity importance quantifies which acoustic feature carries the era signal.",
        "how": "Importances are ranked and shown as a bar chart.",
        "evidence": "bda.ml.supervised.feature_importance",
        "metric": _m_importance,
    },
    {
        "id": "ml-hierarchical",
        "name": "Hierarchical (Ward) clustering + dendrogram",
        "experiment": "Exp.2",
        "co_lo": "CO2 / LO2",
        "category": "Machine learning",
        "summary": "An alternative clustering family that builds a merge tree rather than requiring k up front.",
        "how": "Ward linkage on a sample produces real merge heights, drawn as a dendrogram, and ARI compares it with K-Means.",
        "evidence": "bda.ml.hierarchical",
        "metric": _m_hier,
    },
    {
        "id": "ml-elbow",
        "name": "Elbow method + silhouette sweep",
        "experiment": "Exp.2",
        "co_lo": "CO2 / LO2",
        "category": "Model selection",
        "summary": "Inertia (within-cluster SSE) and silhouette across k=2..10 to justify the chosen k.",
        "how": "Both curves are computed on a bounded sample and plotted side by side.",
        "evidence": "bda.ml.elbow",
        "metric": _m_elbow,
    },
    # ---------------- Exp.3 ---------------- #
    {
        "id": "nosql-mongo",
        "name": "MongoDB document store (schemaless persistence)",
        "experiment": "Exp.3",
        "co_lo": "CO3 / LO3",
        "category": "NoSQL",
        "summary": "Runs are stored as nested documents with a JSON-file fallback when MongoDB is unreachable.",
        "how": "Live collection statistics, document schema paths and a sample document are reported per run.",
        "evidence": "bda.nosql.stats",
        "metric": _m_mongo,
    },
    {
        "id": "nosql-queries",
        "name": "NoSQL queries + aggregation pipeline",
        "experiment": "Exp.3",
        "co_lo": "CO3 / LO3",
        "category": "NoSQL",
        "summary": "CRUD surface, nested-field queries, $lt/$gt comparison, array-contains and $group aggregations.",
        "how": "24 commands are documented; the read-only ones are executed live and their results shown.",
        "evidence": "bda.nosql.commands",
        "metric": _m_mongo_cmds,
    },
    # ---------------- Exp.7 ---------------- #
    {
        "id": "sna-graph",
        "name": "Network construction from a similarity matrix",
        "experiment": "Exp.7",
        "co_lo": "CO5 / LO5",
        "category": "Graph analytics",
        "summary": "A k-NN cosine graph over standardized acoustic vectors stands in for a social graph.",
        "how": "Nodes are sampled tracks; edges connect each track to its most acoustically similar neighbours.",
        "evidence": "bda.graph.stats",
        "metric": _m_sna,
    },
    {
        "id": "sna-degree",
        "name": "Degree centrality + degree distribution",
        "experiment": "Exp.7",
        "co_lo": "CO5 / LO5",
        "category": "Graph analytics",
        "summary": "Degree histogram, clustering coefficient, density, connected components and PageRank influence.",
        "how": "Node size/colour encodes degree; a histogram and a hub leaderboard are rendered.",
        "evidence": "bda.graph.degree_histogram",
        "metric": _m_degree,
    },
    {
        "id": "sna-layouts",
        "name": "Network layouts (force-directed + degree rings)",
        "experiment": "Exp.7",
        "co_lo": "CO5 / LO5",
        "category": "Graph analytics",
        "summary": "Fruchterman-Reingold force layout and a degree-ordered concentric layout.",
        "how": "The layout is computed in the backend and rendered as an interactive SVG graph.",
        "evidence": "bda.graph.layouts",
        "metric": lambda bda, r: " + ".join(_get(bda, "graph.layouts", []) or []) or "—",
    },
    {
        "id": "sna-communities",
        "name": "Community detection (label propagation)",
        "experiment": "Exp.7",
        "co_lo": "CO5 / LO5",
        "category": "Graph analytics",
        "summary": "Communities are found by label propagation and scored with modularity.",
        "how": "Each community is cross-tabbed against the acoustic clusters to show agreement.",
        "evidence": "bda.graph.communities",
        "metric": _m_communities,
    },
    # ---------------- CO4 streaming ---------------- #
    {
        "id": "stream-windows",
        "name": "Tumbling + sliding windows over an event stream",
        "experiment": "CO4",
        "co_lo": "CO4 / LO4",
        "category": "Stream processing",
        "summary": "The static corpus is replayed as a stream of micro-batches with rolling aggregates.",
        "how": "Events are ordered by release year; window means and an EWMA are plotted.",
        "evidence": "bda.streaming.windows",
        "metric": _m_stream,
    },
    {
        "id": "stream-watermark",
        "name": "Watermark & late-arriving events",
        "experiment": "CO4",
        "co_lo": "CO4 / LO4",
        "category": "Stream processing",
        "summary": "Event time vs arrival time, with late events counted against the running maximum.",
        "how": "Arrival order is the frame order; lateness is measured in release years.",
        "evidence": "bda.streaming.stats",
        "metric": _m_late,
    },
    {
        "id": "stream-drift",
        "name": "Concept drift / change-point detection",
        "experiment": "CO4",
        "co_lo": "CO4 / LO4",
        "category": "Stream processing",
        "summary": "A z-score test against the previous rolling window flags distribution shifts.",
        "how": "The decade 'vibe shift' becomes an explicit list of detected change points.",
        "evidence": "bda.streaming.stats.drift_count",
        "metric": _m_drift,
    },
    # ---------------- Exp.8 + statistical computing ---------------- #
    {
        "id": "eda-stats",
        "name": "Descriptive statistics + Pearson correlation",
        "experiment": "Exp.8",
        "co_lo": "CO6 / LO6",
        "category": "Statistics",
        "summary": "Mean/std/quartiles/skew/kurtosis per feature and a full correlation matrix.",
        "how": "Rendered as a correlation heatmap with the strongest pairs called out.",
        "evidence": "bda.eda.correlation",
        "metric": _m_corr,
    },
    {
        "id": "eda-outliers",
        "name": "Outlier & anomaly detection",
        "experiment": "Exp.8",
        "co_lo": "CO6 / LO6",
        "category": "Statistics",
        "summary": "IQR fences per feature plus a multivariate Isolation Forest count.",
        "how": "Flag counts and percentages are shown per feature with the global anomaly rate.",
        "evidence": "bda.eda.outliers",
        "metric": _m_outliers,
    },
    {
        "id": "viz-dashboards",
        "name": "Interactive data visualization",
        "experiment": "Exp.8",
        "co_lo": "CO6 / LO6",
        "category": "Visualization",
        "summary": "Decade×cluster heatmap, cluster-profile heatmap, PCA scatter, trend lines, KD/elbow curves, dendrogram, graph view.",
        "how": "React + Recharts dashboards fed by the run results JSON.",
        "evidence": "results.decades",
        "metric": _m_viz,
    },
    {
        "id": "bench-distributed",
        "name": "Execution benchmarking: distributed vs single-node",
        "experiment": "Exp.2",
        "co_lo": "CO2 / LO2",
        "category": "Performance",
        "summary": "The same aggregation timed in PySpark and in pandas, plus a vectorized-vs-loop baseline.",
        "how": "Every run records the two timings and the speedup factor.",
        "evidence": "results.benchmark",
        "metric": _m_bench,
    },
]


EXPERIMENTS: list[dict[str, Any]] = [
    {"id": "Exp.1", "title": "HDFS basics & Hadoop ecosystem", "co_lo": "CO1 / LO1"},
    {"id": "Exp.2", "title": "ML algorithm with PySpark", "co_lo": "CO2 / LO2"},
    {"id": "Exp.3", "title": "MongoDB / NoSQL commands", "co_lo": "CO3 / LO3"},
    {"id": "Exp.4", "title": "MapReduce word count", "co_lo": "CO2 / LO2"},
    {"id": "Exp.5", "title": "MapReduce: matrix mult, aggregates, joins, sorting, searching", "co_lo": "CO2 / LO2"},
    {"id": "Exp.6", "title": "Bloom filter", "co_lo": "CO4 / LO4"},
    {"id": "Exp.7", "title": "Social network analysis", "co_lo": "CO5 / LO5"},
    {"id": "Exp.8", "title": "Data visualization", "co_lo": "CO6 / LO6"},
    {"id": "CO4", "title": "Stream data techniques (extended)", "co_lo": "CO4 / LO4"},
]


# ---- annotate the registry with the core/additional split ------------------ #
# Done here rather than inline on 33 literals so the selection is easy to change
# in one place (and can never disagree between the API and the UI).

for _concept in CONCEPTS:
    _concept["primary"] = _concept["experiment"] in CORE_EXPERIMENTS

for _experiment in EXPERIMENTS:
    _experiment["core"] = _experiment["id"] in CORE_EXPERIMENTS
