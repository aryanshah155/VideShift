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
    return "\n".join(lines)


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

    cells.append(_md(_results_markdown(results)))

    return nb


def notebook_to_bytes(notebook: dict) -> bytes:
    return json.dumps(notebook, indent=1).encode("utf-8")
