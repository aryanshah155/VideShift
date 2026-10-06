"""Colab notebook export: section-wise .ipynb reproducing the transcript's pipeline.

All hard-won fixes from the transcript are baked in: path auto-detection,
ANSI mode disabled, double->int year casting, and quote/escape-safe CSV reads.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any


def _md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def _code(code: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": code.splitlines(keepends=True),
    }


def _results_markdown(results: dict[str, Any] | None) -> str:
    if not results:
        return "_Run the pipeline in the app to embed actual results here._"
    lines = ["## Run snapshot", ""]
    clusters = results.get("clusters", [])
    if clusters:
        lines.append("| Cluster | Label | Size | Share % |")
        lines.append("|---|---|---|---|")
        for c in clusters:
            lines.append(
                f"| {c['cluster']} | {c.get('label', '')} | {c['size']:,} | {c.get('share_pct', 0)}% |"
            )
        lines.append("")
    decades = results.get("decades", [])
    if decades:
        lines.append("### Decade x cluster shares (%)")
        lines.append("")
        header = "| Decade | " + " | ".join(decades[0]["shares"].keys()) + " |"
        lines.append(header)
        lines.append("|" + "---|" * (len(decades[0]["shares"]) + 1))
        for d in decades:
            row = " | ".join(f"{v:.1f}" for v in d["shares"].values())
            lines.append(f"| {d['decade']}s | {row} |")
        lines.append("")
    bench = results.get("benchmark")
    if bench:
        lines.append(
            f"### Benchmark: {bench['label_a']} {bench['seconds_a']}s vs "
            f"{bench['label_b']} {bench['seconds_b']}s ({bench['speedup']}x)"
        )
        lines.append("")
    lines.extend(_bda_markdown(results.get("bda")))
    return "\n".join(lines)


def _bda_markdown(bda: dict[str, Any] | None) -> list[str]:
    """Render the Big Data Analytics findings as notebook markdown."""
    if not bda:
        return []
    lines: list[str] = [
        "## Big Data Analytics findings",
        "",
        "> **Core portion of this project: Exp.3 (MongoDB / NoSQL), Exp.4–5 "
        "(MapReduce) and Exp.8 (data visualization).** Sections 12, 10 and 16 below "
        "are the submitted work; sections 9, 11, 13, 14 and 15 are additional "
        "analyses that also run on every pipeline execution.",
        "",
    ]

    hdfs = bda.get("hdfs") or {}
    hfile = hdfs.get("file") or {}
    if hfile:
        lines += [
            "### Exp.1 - HDFS",
            "",
            f"| Metric | Value |",
            "|---|---|",
            f"| File | `{hfile.get('path')}` |",
            f"| Size | {hfile.get('size_human')} ({hfile.get('rows'):,} rows x {hfile.get('columns')} cols) |",
            f"| Blocks | {hfile.get('blocks')} x {hfile.get('block_size_mb')} MB |",
            f"| Replication | {hfile.get('replication')} ({hfile.get('stored_human')} on disk) |",
            f"| hdfs commands rendered | {len(hdfs.get('commands', []))} |",
            "",
        ]

    mr = bda.get("mapreduce") or {}
    jobs = mr.get("jobs") or []
    if jobs:
        lines += ["### Exp.4 / Exp.5 - MapReduce", "", "| Job | Map pairs | Combine saved | Output |", "|---|---|---|---|"]
        for job in jobs:
            st = job.get("stats", {})
            top = (job.get("output") or [{}])[0]
            lines.append(
                f"| {job.get('name')} | {st.get('map_output_pairs'):,} | "
                f"{st.get('combine_saved_pct')}% | {top.get('key')} = {top.get('detail')} |"
            )
        lines.append("")

    bloom = bda.get("bloom") or {}
    prod = bloom.get("production") or {}
    if prod:
        lines += [
            "### Exp.6 - Bloom filter",
            "",
            f"- Items indexed: **{prod.get('n'):,}** (of {prod.get('vocabulary_total_distinct'):,} distinct artists)",
            f"- Bits m = **{prod.get('m'):,}**, hashes k = **{prod.get('k')}**, memory **{prod.get('memory_kb')} KB**",
            f"- Fill {prod.get('fill_pct')}%, theoretical FPR **{prod.get('theoretical_fpr')}**, "
            f"empirical FPR **{prod.get('empirical_fpr')}** over {prod.get('probes'):,} probes",
            f"- False negatives: **0** (guaranteed); false positives: {prod.get('false_positives')}",
            "",
        ]

    nosql = bda.get("nosql") or {}
    if nosql.get("commands"):
        lines += [
            "### Exp.3 - NoSQL (MongoDB)",
            "",
            f"- Backend: **{nosql.get('backend')}** (connected: {nosql.get('connected')})",
            f"- Commands documented: **{len(nosql.get('commands', []))}**",
            "",
        ]

    graph = bda.get("graph") or {}
    gstats = graph.get("stats") or {}
    if gstats:
        lines += [
            "### Exp.7 - Social network analysis",
            "",
            f"- Nodes **{gstats.get('nodes')}**, edges **{gstats.get('edges')}**, density {gstats.get('density')}",
            f"- Avg degree {gstats.get('avg_degree')}, avg clustering coefficient {gstats.get('avg_clustering_coefficient')}",
            f"- Communities **{gstats.get('communities')}**, modularity **{gstats.get('modularity')}**, "
            f"components {gstats.get('components')}",
            "",
        ]

    stream = bda.get("streaming") or {}
    sstats = stream.get("stats") or {}
    if sstats:
        lines += [
            "### CO4 - Stream processing",
            "",
            f"- {sstats.get('batches')} micro-batches of {sstats.get('batch_size'):,}, sliding window {sstats.get('window')}",
            f"- Late events {sstats.get('late_events'):,} ({sstats.get('late_pct')}%), "
            f"detected drift points **{sstats.get('drift_count')}**",
            "",
        ]

    ml = bda.get("ml") or {}
    sup = ml.get("supervised") or {}
    if sup.get("models"):
        lines += ["### Exp.2 - Supervised ML", "", f"Target: `{sup.get('target')}`", ""]
        lines += ["| Model | Accuracy | Precision | Recall | F1 | ROC-AUC |", "|---|---|---|---|---|---|"]
        for m in sup["models"]:
            lines.append(
                f"| {m['name']} | {m['accuracy']} | {m['precision']} | {m['recall']} | "
                f"{m['f1']} | {m.get('roc_auc')} |"
            )
        lines.append("")
        imp = sup.get("feature_importance") or {}
        if imp:
            lines.append(
                "Feature importances (RandomForest): "
                + ", ".join(f"`{k}`={v}" for k, v in imp.items())
            )
            lines.append("")
    elbow = (ml.get("elbow") or {})
    if elbow.get("k"):
        lines.append(
            f"Elbow k = **{elbow.get('elbow_k')}**, best silhouette k = "
            f"**{elbow.get('best_silhouette_k')}** across k={elbow.get('k')}."
        )
        lines.append("")
    hier = ml.get("hierarchical") or {}
    if hier.get("rows_used"):
        lines.append(
            f"Hierarchical (Ward) clustering on {hier.get('rows_used')} sampled tracks: "
            f"max merge height {hier.get('max_height')}, ARI vs flat cut "
            f"{hier.get('ari_vs_agglomerative_cut')}."
        )
        lines.append("")

    eda = bda.get("eda") or {}
    if eda.get("strongest_pairs"):
        lines += ["### Exp.8 - Statistics / EDA", "", "| Feature pair | Pearson r |", "|---|---|"]
        for p in eda["strongest_pairs"][:5]:
            lines.append(f"| {p['a']} ~ {p['b']} | {p['r']} |")
        anomaly = eda.get("anomaly") or {}
        lines.append("")
        lines.append(
            f"IQR outlier flags: {eda.get('outlier_flags_total'):,}. "
            f"IsolationForest anomalies: {anomaly.get('count')} of "
            f"{anomaly.get('sampled'):,} sampled ({anomaly.get('pct')}%)."
        )
        lines.append("")
    return lines


def build_notebook(config: dict, results: dict[str, Any] | None = None) -> dict:
    """Build the .ipynb JSON for the given run configuration."""
    k = config.get("k", 5)
    year_from = config.get("year_from", 1960)
    year_to = config.get("year_to", 2023)
    feats = config.get("features") or [
        "danceability", "energy", "valence", "tempo",
        "acousticness", "instrumentalness", "loudness", "speechiness",
    ]
    feats_list = ",\n    ".join(f'"{f}"' for f in feats)

    nb: dict[str, Any] = {
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {
            "colab": {"provenance": [], "name": "Spotify_Vibe_Shift_Clustering.ipynb"},
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "language_info": {"name": "python"},
        },
        "cells": [],
    }
    cells = nb["cells"]

    cells.append(_md(
        f"""# Spotify "Vibe Shift" Acoustic Clustering

Distributed clustering of Spotify audio features with PySpark MLlib to quantify
historical acoustic trends ("vibe shifts") across decades.

**Run configuration used in the app:** `k={k}`, years `{year_from}-{year_to}`,
features: `{", ".join(feats)}`

Fixes baked in from the debugging transcript:
1. Path auto-detection for `tracks_features.csv` (root vs `/content`)
2. `spark.sql.ansi.enabled=false` so malformed CSV rows become NULLs instead of hard errors
3. Safe `year` casting: `double` then `integer` (handles `"2004.0"` strings)
4. Quote/escape handling in CSV parsing for commas inside artist/title strings
5. Explicit `double` casting of feature columns + `dropna`
"""
    ))

    cells.append(_md("## Section 1: Environment Setup & Spark Session Initialization"))
    cells.append(_code(f"""\
# Install PySpark in Google Colab
!pip install -q pyspark

import time
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyspark
import seaborn as sns

# Initialize Spark Session optimized for Colab memory limit
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = (
    SparkSession.builder.appName("Spotify_Vibe_Shift_Clustering")
    .config("spark.driver.memory", "8g")
    .config("spark.execution.arrow.pyspark.enabled", "true")
    .config("spark.sql.ansi.enabled", "false")  # Prevents hard crashes on malformed CSV rows
    .getOrCreate()
)

print(f"Spark Version: {{spark.version}}")
"""))

    cells.append(_md("## Section 2: Kaggle Dataset Download & Data Ingestion"))
    cells.append(_code("""\
import os

# Option A: Download directly using Kaggle API (Requires API Token)
# Upload your 'kaggle.json' file to Colab root directory first
if os.path.exists("kaggle.json"):
  !mkdir -p ~/.kaggle
  !cp kaggle.json ~/.kaggle/
  !chmod 600 ~/.kaggle/kaggle.json
  !kaggle datasets download -d rodolfofigueroa/spotify-12m-songs
  !unzip -o spotify-12m-songs.zip
else:
  print("`kaggle.json` not found. Assuming 'tracks_features.csv' is uploaded.")

# FIX: Automatically locate tracks_features.csv wherever it was saved
if os.path.exists("/tracks_features.csv"):
  csv_path = "/tracks_features.csv"
elif os.path.exists("/content/tracks_features.csv"):
  csv_path = "/content/tracks_features.csv"
else:
  csv_path = "tracks_features.csv"

print(f"Loading dataset from: {{csv_path}}")

# FIX: quote/escape parameters handle commas inside text fields
df_raw = spark.read.csv(
    csv_path, header=True, inferSchema=True, quote='"', escape='"'
)

print(f"Total Rows Ingested: {{df_raw.count():,}}")
df_raw.printSchema()
"""))

    cells.append(_md("## Section 3: Data Cleaning & Feature Engineering"))
    cells.append(_code(f"""\
# FIX: ANSI mode off so malformed strings become NULL instead of raising
spark.conf.set("spark.sql.ansi.enabled", "false")

feature_cols = [
    {feats_list},
]

# Select core columns and cast features explicitly (malformed -> NULL)
df_clean = df_raw.select(
    ["id", "name", "artists", "year", "release_date"] + feature_cols
)

for c in feature_cols:
  df_clean = df_clean.withColumn(c, F.col(c).cast("double"))

# FIX: cast year through double to parse decimal strings ("2004.0")
df_clean = (
    df_clean.withColumn("year", F.col("year").cast("double").cast("integer"))
    .filter((F.col("year") >= {year_from}) & (F.col("year") <= {year_to}))
    .withColumn("decade", (F.floor(F.col("year") / 10) * 10).cast("integer"))
)

df_clean = df_clean.dropna()

df_clean.cache()
print(f"Cleaned Row Count: {{df_clean.count():,}}")
df_clean.select("name", "artists", "year", "decade", "energy").show(5)
"""))

    cells.append(_md("## Section 4: MLlib Preprocessing (VectorAssembler & StandardScaler)"))
    cells.append(_code("""\
from pyspark.ml.feature import StandardScaler, VectorAssembler

# Assemble individual numerical columns into a single vector column
assembler = VectorAssembler(inputCols=feature_cols, outputCol="raw_features")
df_assembled = assembler.transform(df_clean)

# Standardize features (Mean=0, StdDev=1) so high-range variables like
# Tempo don't bias the K-Means distance metric
scaler = StandardScaler(
    inputCol="raw_features",
    outputCol="scaled_features",
    withStd=True,
    withMean=True,
)
scaler_model = scaler.fit(df_assembled)
df_scaled = scaler_model.transform(df_assembled)

df_scaled.select("raw_features", "scaled_features").show(2, truncate=False)
"""))

    cells.append(_md("## Section 5: Distributed K-Means Clustering & PCA Reduction"))
    cells.append(_code(f"""\
from pyspark.ml.clustering import KMeans
from pyspark.ml.feature import PCA

# Fit PySpark Distributed K-Means Model (k={k} acoustic profiles)
kmeans = KMeans(
    featuresCol="scaled_features", predictionCol="cluster", k={k}, seed=42
)
kmeans_model = kmeans.fit(df_scaled)
df_clustered = kmeans_model.transform(df_scaled)

# Dimensionality reduction (8D -> 2D PCA) for visualization
pca = PCA(k=2, inputCol="scaled_features", outputCol="pca_features")
pca_model = pca.fit(df_clustered)
df_pca = pca_model.transform(df_clustered)

df_pca.cache()
df_pca.select("name", "cluster", "pca_features").show(5)
"""))

    cells.append(_md("## Section 6: Historical 'Vibe Shift' Aggregation"))
    cells.append(_code("""\
# Group by decade and cluster to quantify acoustic distribution per era
decade_cluster_df = df_pca.groupBy("decade", "cluster").count()

# Pivot data in PySpark SQL
vibe_pivot = (
    decade_cluster_df.groupBy("decade")
    .pivot("cluster")
    .sum("count")
    .fillna(0)
    .orderBy("decade")
)

# Convert aggregated summary table to Pandas for plotting
pd_vibe = vibe_pivot.toPandas().set_index("decade")

# Normalize counts into row-wise percentages
pd_vibe_pct = pd_vibe.div(pd_vibe.sum(axis=1), axis=0) * 100

print("Decade Acoustic Cluster Distribution (%):")
print(pd_vibe_pct.round(2))
"""))

    cells.append(_md("## Section 7: Visualizations (Vibe Shift Heatmap & Cluster Profiles)"))
    cells.append(_code("""\
plt.figure(figsize=(12, 6))
sns.heatmap(
    pd_vibe_pct,
    annot=True,
    fmt=".1f",
    cmap="YlGnBu",
    cbar_kws={"label": "Percentage of Decade Tracks (%)"},
)
plt.title("Historical Vibe Shift: Evolution of Spotify Acoustic Clusters (1960s-2020s)")
plt.xlabel("Acoustic Cluster ID")
plt.ylabel("Decade")
plt.show()

# Calculate Mean Feature Values per Cluster to interpret profile characteristics
cluster_profiles = (
    df_clustered.groupBy("cluster").mean(*feature_cols).toPandas()
)
cluster_profiles = cluster_profiles.set_index("cluster")
cluster_profiles.columns = [c.replace("avg(", "").replace(")", "") for c in cluster_profiles.columns]

plt.figure(figsize=(14, 5))
sns.heatmap(cluster_profiles.T, annot=True, fmt=".2f", cmap="coolwarm")
plt.title("Cluster Profiles: Mean Audio Feature Values")
plt.xlabel("Cluster ID")
plt.ylabel("Acoustic Feature")
plt.show()
"""))

    cells.append(_md("## Section 8: Execution Benchmarking (PySpark vs Single-Node Pandas)"))
    cells.append(_code("""\
# Performance Test: Multi-variable GroupBy & Aggregation across all records

# 1. PySpark Timer
start_spark = time.time()
spark_res = (
    df_clean.groupBy("decade")
    .agg(
        F.avg("danceability"),
        F.avg("energy"),
        F.avg("valence"),
        F.avg("acousticness"),
    )
    .collect()
)
spark_time = time.time() - start_spark

# 2. Pandas Timer (Converting clean dataset to Pandas DataFrame)
pd_df = df_clean.select(
    "decade", "danceability", "energy", "valence", "acousticness"
).toPandas()

start_pd = time.time()
pd_res = pd_df.groupby("decade").agg(
    {"danceability": "mean", "energy": "mean", "valence": "mean", "acousticness": "mean"}
)
pd_time = time.time() - start_pd

print(f"PySpark Execution Time : {{spark_time:.4f}} seconds")
print(f"Pandas Execution Time  : {{pd_time:.4f}} seconds")
print(f"Speedup Factor         : {{pd_time / spark_time:.2f}}x faster on PySpark")
"""))

    cells.append(_md("""
## Section 9 (Exp.1): HDFS / Hadoop - block layout & replica placement

HDFS stores a file as fixed-size **blocks**, each replicated (default 3x) across
DataNodes with rack-aware placement. The cell below computes the block map and
DataNode occupancy for the ingested CSV, then the transcript cell below it prints
the `hdfs dfs` / `hdfs dfsadmin` command set the lab manual asks for.

> On a real cluster these commands run in the Cloudera VM terminal. Here the
> arithmetic is reproduced in Python so every number in the report is *our* data's.
"""))
    cells.append(_code("""\
import math
from pathlib import Path

BLOCK_MB = 128          # dfs.blocksize default
REPLICATION = 3         # dfs.replication default
DATANODES = [
    {"node": "datanode-01", "rack": "/rack1", "ip": "10.0.0.11"},
    {"node": "datanode-02", "rack": "/rack1", "ip": "10.0.0.12"},
    {"node": "datanode-03", "rack": "/rack2", "ip": "10.0.0.13"},
    {"node": "datanode-04", "rack": "/rack2", "ip": "10.0.0.14"},
]

size_bytes = Path(csv_path).stat().st_size
block_bytes = BLOCK_MB * 1024 * 1024
n_blocks = max(1, math.ceil(size_bytes / block_bytes))

print(f"Local file  : {csv_path}")
print(f"Size        : {size_bytes:,} bytes ({size_bytes / 1024**2:.2f} MB)")
print(f"Block size  : {BLOCK_MB} MB")
print(f"Blocks      : {n_blocks}")
print(f"Replication : {REPLICATION} -> {size_bytes * REPLICATION / 1024**2:.2f} MB stored")
print()
print("Block map (rack-aware placement):")
for b in range(n_blocks):
    start = b * block_bytes
    size = min(block_bytes, size_bytes - start)
    replicas = ", ".join(
        DATANODES[(b + i) % len(DATANODES)]["node"]
        + DATANODES[(b + i) % len(DATANODES)]["rack"]
        for i in range(REPLICATION)
    )
    print(f"  blk_{b}: offset={start:,} len={size:,} -> {replicas}")

occupancy = {d["node"]: 0 for d in DATANODES}
for b in range(n_blocks):
    for i in range(REPLICATION):
        occupancy[DATANODES[(b + i) % len(DATANODES)]["node"]] += 1
print()
print("DataNode occupancy (blocks):", occupancy)
"""))
    _hdfs_cell = _hdfs_transcript(results)
    if _hdfs_cell:
        cells.append(_md(_hdfs_cell))

    cells.append(_md("""
## Section 10 (Exp.4 / Exp.5): MapReduce

A minimal but faithful MapReduce runtime: **map -> partition -> combine ->
shuffle -> reduce**, each phase timed and counted. It runs the same jobs the app
shows in its MapReduce panel: word count, per-decade aggregates, a map-side join,
top-N sorting and an inverted index for search.
"""))
    cells.append(_code("""\
import re
import time
import zlib
from collections import defaultdict

STOPWORDS = {"the", "a", "an", "of", "to", "in", "on", "for", "with", "feat", "ft", "you", "me", "my"}
TOKEN_RE = re.compile(r"[a-z']{3,}")
NUM_PARTITIONS = 4


def mapreduce(records, map_fn, reduce_fn, combine_fn=None, num_partitions=NUM_PARTITIONS):
    # Run one MapReduce job and return (output, stats)
    t0 = time.perf_counter()
    pairs = []
    for record in records:
        pairs.extend(map_fn(record))
    map_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    groups = [defaultdict(list) for _ in range(num_partitions)]
    for key, value in pairs:
        groups[zlib.crc32(str(key).encode()) % num_partitions][key].append(value)
    shuffle_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    combined = 0
    if combine_fn is not None:
        for group in groups:
            for key, values in list(group.items()):
                group[key] = [combine_fn(key, values)]
                combined += 1
    combine_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    output = [(key, reduce_fn(key, values)) for group in groups for key, values in group.items()]
    reduce_seconds = time.perf_counter() - t0

    stats = {
        "input_records": len(records),
        "map_output_pairs": len(pairs),
        "combine_output_pairs": combined or len(pairs),
        "combine_saved_pct": round(100 * (len(pairs) - (combined or len(pairs))) / max(1, len(pairs)), 2),
        "unique_keys": sum(len(g) for g in groups),
        "map_s": round(map_seconds, 4),
        "shuffle_s": round(shuffle_seconds, 4),
        "combine_s": round(combine_seconds, 4),
        "reduce_s": round(reduce_seconds, 4),
    }
    return output, stats


# ---- Exp.4: word count over track titles ------------------------------- #
# Collect the labelled rows once; every later section reuses this frame.
pdf = df_clean.select("name", "artists", "year", "decade", *feature_cols).toPandas()
records = pdf.to_dict("records")

def tokenize(text):
    if text is None:
        return []
    return [t for t in TOKEN_RE.findall(str(text).lower()) if t not in STOPWORDS]

word_out, word_stats = mapreduce(
    records,
    map_fn=lambda r: [(t, 1) for t in tokenize(r["name"])],
    reduce_fn=lambda k, vs: sum(vs),
    combine_fn=lambda k, vs: sum(vs),
)
print("Exp.4 word count:")
print("  stats:", word_stats)
for word, count in sorted(word_out, key=lambda kv: -kv[1])[:15]:
    print(f"  {word:<16} {count}")

# ---- Exp.5: per-decade aggregates (combiner shrinks the shuffle) -------- #
agg_cols = feature_cols[:4]

def map_agg(r):
    return [(int(r["decade"]), tuple([1] + [float(r[c]) for c in agg_cols]))]

def combine_agg(key, values):
    acc = [0.0] * (len(agg_cols) + 1)
    for v in values:
        for i, item in enumerate(v):
            acc[i] += item
    return tuple(acc)

def reduce_agg(key, values):
    acc = values[0]
    n = max(1, acc[0])
    return {c: round(acc[i + 1] / n, 4) for i, c in enumerate(agg_cols)}

agg_out, agg_stats = mapreduce(records, map_agg, reduce_agg, combine_agg)
print("\\nExp.5 per-decade aggregates:")
print("  stats:", agg_stats)
for decade, means in sorted(agg_out):
    print(f"  {decade}s {means}")

# ---- Exp.5: top-N sorting --------------------------------------------- #
artist_out, artist_stats = mapreduce(
    records,
    map_fn=lambda r: [
        (a.strip(), 1)
        for a in str(r["artists"]).strip("[]").replace("'", "").split(",")
        if a.strip()
    ],
    reduce_fn=lambda k, vs: sum(vs),
    combine_fn=lambda k, vs: sum(vs),
)
print("\\nExp.5 top artists:")
for artist, count in sorted(artist_out, key=lambda kv: -kv[1])[:10]:
    print(f"  {artist:<30} {count}")

# ---- Exp.5: inverted index (searching) --------------------------------- #
index_out, index_stats = mapreduce(
    records,
    map_fn=lambda r: [(t, r["name"]) for t in tokenize(r["name"])],
    reduce_fn=lambda k, vs: vs[:8],
    combine_fn=lambda k, vs: vs[:8],
)
index = dict(index_out)
print("\\nExp.5 inverted index: %d distinct tokens" % len(index))
for term in list(index)[:3]:
    print(f"  {term!r} -> {index[term]}")
"""))

    cells.append(_md("""
## Section 11 (Exp.6): Bloom filter

A Bloom filter is a bit array of *m* bits plus *k* hash functions. Inserting sets
*k* bits; querying returns "definitely absent" or "possibly present". It has **no
false negatives** and a tunable false-positive rate
`p = (1 - e^(-kn/m))^k`. Here it indexes the artist vocabulary so a track search
can skip a Parquet scan entirely, and the lab's ASCII -> hash -> bit table is run
at small scale.
"""))
    cells.append(_code("""\
import hashlib
import math


class BloomFilter:
    def __init__(self, m_bits, k):
        self.m = max(1, int(m_bits))
        self.k = max(1, int(k))
        self.bits = bytearray((self.m + 7) // 8)
        self.inserted = 0

    @staticmethod
    def optimal_m(n, p=0.01):
        return int(math.ceil(-max(1, n) * math.log(p) / (math.log(2) ** 2)))

    @staticmethod
    def optimal_k(m, n):
        return max(1, int(round((m / max(1, n)) * math.log(2))))

    def positions(self, item):
        data = str(item).encode("utf-8", "ignore")
        h1 = int.from_bytes(hashlib.blake2b(data, digest_size=8).digest(), "big")
        h2 = int.from_bytes(hashlib.sha256(data).digest()[:8], "big") | 1
        return [((h1 + i * h2) % self.m) for i in range(self.k)]

    def add(self, item):
        pos = self.positions(item)
        for p in pos:
            self.bits[p >> 3] |= 1 << (p & 7)
        self.inserted += 1
        return pos

    def contains(self, item):
        return all(self.bits[p >> 3] & (1 << (p & 7)) for p in self.positions(item))

    def fpr(self):
        return (1 - math.exp(-self.k * self.inserted / self.m)) ** self.k

    def bits_set(self):
        return sum(bin(b).count("1") for b in self.bits)


# ---- lab exercise: 5 words in, 5 words tested -> TP / FP / Not present -- #
lab = BloomFilter(32, 3)
for word in ["hadoop", "spark", "mapreduce", "nosql", "bloom"]:
    lab.add(word)

print("word         ascii_sum  bit_positions        result")
for word in ["spark", "bloom", "cluster", "stream", "hbase"]:
    pos = lab.positions(word)
    hit = lab.contains(word)
    status = "True positive" if word in ("hadoop", "spark", "mapreduce", "nosql", "bloom") else ("False positive" if hit else "Not present")
    print(f"{word:<12} {sum(ord(c) for c in word):<9} {str(pos):<20} {status}")

print("\\nbit array after inserts:", "".join("1" if lab.bits[i >> 3] & (1 << (i & 7)) else "0" for i in range(32)))
print(f"fill = {100 * lab.bits_set() / 32:.1f}%   theoretical FPR = {lab.fpr():.4f}")

# ---- production filter over the artist vocabulary ---------------------- #
artists = set()
for value in pdf["artists"].astype(str):
    for part in value.strip("[]").replace("'", "").split(","):
        part = part.strip()
        if part and part.lower() != "nan":
            artists.add(part)
artists = sorted(artists)[:40000]

m = BloomFilter.optimal_m(len(artists), 0.01)
k = BloomFilter.optimal_k(m, len(artists))
prod = BloomFilter(m, k)
for artist in artists:
    prod.add(artist)

probes = [f"zz-absent-{i}" for i in range(2000)]
fp = sum(1 for p in probes if prod.contains(p))
print(f"\\nProduction filter: n={len(artists):,} m={m:,} k={k} "
      f"fill={100 * prod.bits_set() / m:.2f}% memory={len(prod.bits) / 1024:.1f} KB")
print(f"  theoretical FPR = {prod.fpr():.6f}   empirical FPR = {fp / len(probes):.6f} "
      f"({fp} false positives / {len(probes)} probes)")
print(f"  false negatives  = 0 (every inserted artist verified present: "
      f"{sum(prod.contains(a) for a in artists[:500])}/500)")
"""))

    cells.append(_md("""
## Section 12 (Exp.3): NoSQL with MongoDB

The lab installs MongoDB and runs 20+ commands. VibeShift stores every run as a
**schemaless document** (nested `config`, `stages[]`, `results_summary`), with a
JSON-file fallback when the server is down.
"""))
    cells.append(_code("""\
# Start the server, then connect:
#   mongod --dbpath C:\\mongodb\\data\\db
#   mongosh
#
# Equivalent PyMongo usage used by the VibeShift API:
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
db = client["vibeshift"]
runs = db["runs"]

# insertOne - the runner writes one document per run
run_doc = {
    "id": "demo0001",
    "state": "done",
    "engine": "pandas",
    "config": {"k": 5, "year_from": 1960, "year_to": 2023, "features": feature_cols},
    "results_summary": {"silhouette": 0.12, "rows_clean": 859377},
}
runs.update_one({"id": run_doc["id"]}, {"$set": run_doc}, upsert=True)

# find / findOne / countDocuments
print("documents        :", runs.count_documents({}))
print("done runs        :", runs.count_documents({"state": "done"}))
print("k == 5           :", runs.count_documents({"config.k": 5}))
print("year_from < 2000 :", runs.count_documents({"config.year_from": {"$lt": 2000}}))
print("features has item:", runs.count_documents({"config.features": "energy"}))
print("one document     :", runs.find_one({"id": "demo0001"}, {"_id": 0}))

# aggregation pipeline: group by state
pipeline = [{"$group": {"_id": "$state", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}]
print("by state         :", list(runs.aggregate(pipeline)))
print("distinct engines :", runs.distinct("engine"))
print("indexes          :", list(runs.index_information()))
"""))
    _nosql_cell = _nosql_transcript(results)
    if _nosql_cell:
        cells.append(_md(_nosql_cell))

    cells.append(_md("""
## Section 13 (Exp.7): Social network analysis

The lab builds a network in R/igraph, plots the degree histogram, draws the graph
with layouts and detects communities. The Spotify corpus has no explicit social
edges, so the network is an **acoustic similarity graph**: nodes are sampled
tracks, edges connect each track to its nearest neighbours in standardized
feature space.
"""))
    cells.append(_code("""\
import numpy as np
import networkx as nx

sample = pdf.sample(n=min(200, len(pdf)), random_state=42).reset_index(drop=True)
X = sample[feature_cols].to_numpy(dtype=float)
X = (X - X.mean(0)) / np.where(X.std(0) == 0, 1, X.std(0))
Xn = X / np.linalg.norm(X, axis=1, keepdims=True)
S = Xn @ Xn.T
np.fill_diagonal(S, -2)

K = 4
neighbours = np.argsort(-S, axis=1)[:, :K]
G = nx.Graph()
for i in range(len(sample)):
    G.add_node(i, label=str(sample.loc[i, "name"])[:30])
for i in range(len(sample)):
    for j in neighbours[i]:
        G.add_edge(int(i), int(j), weight=float(S[i, int(j)]))

print("nodes:", G.number_of_nodes(), "edges:", G.number_of_edges())
print("density:", round(nx.density(G), 4))
print("components:", nx.number_connected_components(G))
print("avg clustering coefficient:", round(nx.average_clustering(G), 4))

# 4. Histogram of node degree
degrees = [d for _, d in G.degree()]
plt.figure(figsize=(8, 4))
plt.hist(degrees, bins=range(min(degrees), max(degrees) + 2))
plt.title("Histogram of node degree")
plt.xlabel("degree")
plt.ylabel("count")
plt.show()

# 6. Highlighting degrees & layouts
pos = nx.spring_layout(G, seed=42)
plt.figure(figsize=(11, 9))
nx.draw_networkx_edges(G, pos, alpha=0.25)
nx.draw_networkx_nodes(
    G, pos,
    node_size=[60 + 45 * d for d in degrees],
    node_color=degrees,
    cmap="viridis",
)
plt.title("Acoustic similarity network (node size/colour = degree)")
plt.axis("off")
plt.show()

# 7. Community detection
communities = nx.community.label_propagation_communities(G)
communities = sorted(communities, key=len, reverse=True)
print("communities found:", len(communities))
print("sizes:", [len(c) for c in communities][:10])
print("modularity:", round(nx.community.modularity(G, communities), 4))

plt.figure(figsize=(11, 9))
colors = {}
for idx, community in enumerate(communities):
    for node in community:
        colors[node] = idx
nx.draw_networkx_edges(G, pos, alpha=0.2)
nx.draw_networkx_nodes(G, pos, node_size=90, node_color=[colors[n] for n in G.nodes()], cmap="tab20")
plt.title("Community detection on the acoustic similarity graph")
plt.axis("off")
plt.show()

# PageRank influence ranking
top_pr = sorted(nx.pagerank(G).items(), key=lambda kv: -kv[1])[:10]
print("top PageRank nodes:")
for node, score in top_pr:
    print(f"  {G.nodes[node]['label']:<32} {score:.5f}")
"""))

    cells.append(_md("""
## Section 14 (CO4): Stream processing on the same corpus

Streaming has no meaning on a static CSV, so the corpus is replayed as an event
stream: events are ordered by release year (event time) while the frame row order
plays the role of arrival order. Any event behind the running maximum is a late
arrival - what a watermark exists to absorb. Windows are then aggregated and a
z-score on the window's **step** flags concept drift (a trend is not drift; a jump
in the rate of change is).
"""))
    cells.append(_code("""\
stream_cols = [c for c in ["energy", "acousticness", "valence", "danceability"] if c in feature_cols]
events = pdf[["year", *stream_cols]].dropna()

event_year = events["year"].to_numpy(dtype=float)
running_max = np.maximum.accumulate(event_year)
late = event_year[1:] < running_max[:-1]
print(f"events        : {len(events):,}")
print(f"late arrivals : {late.sum():,} ({100 * late.mean():.2f}%) behind the watermark")
print(f"max lateness  : {float((running_max[1:] - event_year[1:])[late].max()) if late.any() else 0} years")

ordered = events.sort_values("year", kind="mergesort").reset_index(drop=True)
BATCH = max(200, int(np.ceil(len(ordered) / 60)))
WINDOW = 3

windows = []
for b in range(0, len(ordered), BATCH):
    chunk = ordered.iloc[b : b + BATCH]
    windows.append({"batch": len(windows), "year": int(chunk["year"].min()), **{c: chunk[c].mean() for c in stream_cols}})
wdf = pd.DataFrame(windows)
wdf["rolling"] = wdf[stream_cols].rolling(WINDOW, min_periods=1).mean().iloc[:, 0]

# Tumbling window means + drift detection on the rolling step
delta = wdf[stream_cols].rolling(WINDOW, min_periods=1).mean().diff()
HIST = 8
drifts = []
for b in range(HIST + 1, len(delta)):
    hist = delta.iloc[b - HIST : b][stream_cols[0]].to_numpy(dtype=float)
    hist = hist[np.isfinite(hist)]
    if len(hist) < 3 or hist.std() == 0:
        continue
    z = (delta.iloc[b][stream_cols[0]] - hist.mean()) / hist.std()
    if abs(z) > 2.5:
        drifts.append((int(wdf.loc[b, "batch"]), int(wdf.loc[b, "year"]), round(float(z), 3)))
print(f"micro-batches : {len(wdf)} of {BATCH:,} events, sliding window {WINDOW}")
print(f"drift points  : {len(drifts)} -> {drifts[:8]}")

fig, ax = plt.subplots(figsize=(11, 4))
for c in stream_cols:
    ax.plot(wdf["year"], wdf[c].rolling(WINDOW, min_periods=1).mean(), label=c)
for _, year, _z in drifts[:10]:
    ax.axvline(year, color="red", alpha=0.25)
ax.set_title("Streaming window means (red lines = detected drift points)")
ax.set_xlabel("release year (event time)")
ax.legend()
plt.show()
"""))

    cells.append(_md("""
## Section 15 (Exp.2): Supervised learning + model selection

The manual asks for a 70/30 `randomSplit([0.7, 0.3], seed=42)`, relevant metrics
and a feature-importance plot. Target: **is a track modern (year >= 2000)**,
predicted purely from acoustic features. The elbow and silhouette curves show how
k was chosen, and Ward hierarchical clustering gives a second view on structure.
"""))
    cells.append(_code("""\
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score, roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

ml = pdf.dropna(subset=feature_cols).sample(n=min(40000, len(pdf)), random_state=42)
X = ml[feature_cols].to_numpy(dtype=float)
y = (ml["year"] >= 2000).astype(int).to_numpy()

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
print(f"train {len(X_train):,} / test {len(X_test):,}  |  positive class rate {y.mean():.3f}")

models = {
    "RandomForest": RandomForestClassifier(n_estimators=100, random_state=42),
    "DecisionTree": DecisionTreeClassifier(random_state=42, max_depth=8),
    "LogisticRegression": LogisticRegression(max_iter=1000, random_state=42),
}
print(f"{'model':<20}{'acc':>8}{'prec':>8}{'recall':>8}{'f1':>8}{'auc':>8}")
best_name, best_f1, best_model, best_pred = None, -1, None, None
for name, model in models.items():
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    f1 = f1_score(y_test, pred)
    print(f"{name:<20}{accuracy_score(y_test, pred):>8.4f}{precision_score(y_test, pred):>8.4f}"
          f"{recall_score(y_test, pred):>8.4f}{f1:>8.4f}{auc:>8.4f}")
    if f1 > best_f1:
        best_name, best_f1, best_model, best_pred = name, f1, model, pred

print(f"\\nbest model: {best_name}")
print("confusion matrix [[TN, FP], [FN, TP]]:", confusion_matrix(y_test, best_pred, labels=[0, 1]).tolist())

# Feature importance
importance = pd.Series(models["RandomForest"].feature_importances_, index=feature_cols).sort_values()
plt.figure(figsize=(8, 4))
importance.plot(kind="barh")
plt.title("Random-Forest feature importance (era prediction)")
plt.xlabel("importance")
plt.show()

# ROC curve
fpr, tpr, _ = roc_curve(y_test, best_model.predict_proba(X_test)[:, 1])
plt.figure(figsize=(5, 5))
plt.plot(fpr, tpr, label=f"AUC = {roc_auc_score(y_test, best_model.predict_proba(X_test)[:, 1]):.3f}")
plt.plot([0, 1], [0, 1], "--", color="grey")
plt.xlabel("false positive rate")
plt.ylabel("true positive rate")
plt.title("ROC curve")
plt.legend()
plt.show()

# Elbow + silhouette (unsupervised model selection)
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

Xs = (X[:15000] - X[:15000].mean(0)) / np.where(X[:15000].std(0) == 0, 1, X[:15000].std(0))
inertias, silhouettes = [], []
for k in range(2, 11):
    km = KMeans(n_clusters=k, n_init=3, random_state=42).fit(Xs)
    labels = km.labels_
    inertias.append(km.inertia_)
    idx = np.random.default_rng(42).choice(len(Xs), size=min(3000, len(Xs)), replace=False)
    silhouettes.append(silhouette_score(Xs[idx], labels[idx]))

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
ax1.plot(range(2, 11), inertias, marker="o")
ax1.set_title("Elbow: within-cluster SSE")
ax1.set_xlabel("k")
ax2.plot(range(2, 11), silhouettes, marker="o", color="orange")
ax2.set_title("Silhouette score")
ax2.set_xlabel("k")
plt.show()

# Hierarchical (Ward) clustering + dendrogram
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from sklearn.metrics import adjusted_rand_score

h = pdf.sample(n=min(120, len(pdf)), random_state=42)
Xh = h[feature_cols].to_numpy(dtype=float)
Xh = (Xh - Xh.mean(0)) / np.where(Xh.std(0) == 0, 1, Xh.std(0))
Z = linkage(Xh, method="ward")

plt.figure(figsize=(12, 4))
dendrogram(Z, labels=[str(n)[:14] for n in h["name"]], leaf_rotation=90, leaf_font_size=6)
plt.title("Hierarchical clustering dendrogram (Ward linkage)")
plt.ylabel("merge height")
plt.show()

from sklearn.cluster import AgglomerativeClustering
hier_labels = fcluster(Z, t=5, criterion="maxclust")
flat_labels = AgglomerativeClustering(n_clusters=5, linkage="ward").fit_predict(Xh)
print("ARI between hierarchical cut and flat Ward clustering:", round(adjusted_rand_score(hier_labels, flat_labels), 4))
"""))

    cells.append(_md("""
## Section 16 (Exp.8): Descriptive statistics, correlation and outliers

Statistical computing plus the graphics the manual expects: a correlation heatmap
over the acoustic features, per-feature IQR outlier counts and a multivariate
IsolationForest anomaly count.
"""))
    cells.append(_code("""\
from sklearn.ensemble import IsolationForest

print(pdf[feature_cols].describe().T[["mean", "std", "min", "50%", "max"]])

corr = pdf[feature_cols].corr(method="pearson")
plt.figure(figsize=(8, 6))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0)
plt.title("Pearson correlation between acoustic features")
plt.show()

q1 = pdf[feature_cols].quantile(0.25)
q3 = pdf[feature_cols].quantile(0.75)
iqr = q3 - q1
flags = ((pdf[feature_cols] < q1 - 1.5 * iqr) | (pdf[feature_cols] > q3 + 1.5 * iqr)).sum()
print("\\nIQR outlier flags per feature:")
print(flags.to_string())
print("total flags:", int(flags.sum()))

sample_iso = pdf[feature_cols].sample(n=min(20000, len(pdf)), random_state=42)
pred = IsolationForest(contamination=0.02, random_state=42).fit_predict(sample_iso)
print(f"\\nIsolationForest anomalies: {(pred == -1).sum():,} of {len(sample_iso):,} sampled "
      f"({100 * (pred == -1).mean():.2f}%)")
"""))

    cells.append(_md(_results_markdown(results)))

    return nb


def _hdfs_transcript(results: dict[str, Any] | None) -> str:
    """Markdown cell holding the executed hdfs command transcript for the report."""
    commands = ((results or {}).get("bda") or {}).get("hdfs", {}).get("commands") or []
    if not commands:
        return ""
    lines = [
        "### hdfs command transcript (as run in the VibeShift pipeline)",
        "",
        "Copy these into the lab report's Result/Observation section.",
        "",
        "```bash",
    ]
    for entry in commands:
        lines.append(f"$ {entry['cmd']}")
        output = str(entry.get("output", "")).rstrip("\n")
        if output:
            lines.extend(output.splitlines())
        lines.append("")
    lines.append("```")
    return "\n".join(lines)


def _nosql_transcript(results: dict[str, Any] | None) -> str:
    """Markdown cell holding the NoSQL command list with live results."""
    nosql = ((results or {}).get("bda") or {}).get("nosql") or {}
    commands = nosql.get("commands") or []
    if not commands:
        return ""
    lines = [
        f"### MongoDB command transcript ({len(commands)} commands, "
        f"backend: {nosql.get('backend')})",
        "",
        "| # | Command | Purpose | Result |",
        "|---|---|---|---|",
    ]
    for i, entry in enumerate(commands, start=1):
        result = str(entry.get("result", "")).replace("|", "\\|")
        lines.append(f"| {i} | `{entry['cmd']}` | {entry.get('purpose', '')} | {result} |")
    return "\n".join(lines)


def notebook_to_bytes(notebook: dict) -> bytes:
    return json.dumps(notebook, indent=1).encode("utf-8")
