"""Single-node engine: pandas + scikit-learn mirror of the Spark pipeline.

Every stage matches the PySpark engine (same casts, same scaler semantics,
same k-means seed) so results are comparable and the benchmark is honest.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

from ..schema import FEATURE_COLS
from ..schemas import RunConfig
from .base import stage_progress
from .prepare import clean_dataframe, sample_dataframe, to_feature_matrix

CLUSTER_LABELS = {
    0: "Acoustic / Organic",
    1: "High-Energy Electronic",
    2: "Vocal / Pop",
    3: "Instrumental / Ambient",
    4: "Rhythmic / Dance",
    5: "Mellow / Low-Energy",
    6: "Spoken / Lyrical",
    7: "Bright / Upbeat",
    8: "Dark / Intense",
    9: "Experimental / Hybrid",
    10: "Live / Raw",
    11: "Studio / Polished",
}


def _label_for(cluster_id: int) -> str:
    return CLUSTER_LABELS.get(cluster_id, f"Profile {cluster_id}")


def _pure_python_groupby_mean(
    decade_vals: list[tuple[int, list[float]]],
) -> dict[int, list[float]]:
    """Deliberately naive aggregation used as the benchmark's slow baseline."""
    acc: dict[int, list[float]] = {}
    for decade, vals in decade_vals:
        if decade not in acc:
            acc[decade] = [0.0] * len(vals)
        for i, v in enumerate(vals):
            acc[decade][i] += v
    counts: dict[int, int] = {}
    for decade, _ in decade_vals:
        counts[decade] = counts.get(decade, 0) + 1
    return {d: [v / counts[d] for v in vals] for d, vals in acc.items()}


class PandasEngine:
    name = "pandas"

    def run(
        self,
        df: pd.DataFrame,
        config: RunConfig,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        p = stage_progress("prepare", progress)
        feature_cols = [c for c in config.features if c in df.columns] or list(FEATURE_COLS)

        # ---- Stage: clean -------------------------------------------------
        t0 = time.perf_counter()
        df_clean = clean_dataframe(df, config, progress=p)
        df_clean = sample_dataframe(df_clean, config, progress=p)
        clean_seconds = time.perf_counter() - t0

        # ---- Stage: assemble + scale --------------------------------------
        t0 = time.perf_counter()
        X = to_feature_matrix(df_clean, feature_cols)
        assemble_seconds = time.perf_counter() - t0
        if progress:
            progress(f"[assemble] standardized matrix {X.shape} in {assemble_seconds:.2f}s")

        # ---- Stage: kmeans (optional best-k sweep) ------------------------
        t0 = time.perf_counter()
        best_k = None
        silhouette_by_k: dict[str, float] = {}

        def _fit(k: int) -> tuple[KMeans, np.ndarray, float | None]:
            km = KMeans(n_clusters=k, n_init=4, random_state=42)
            labels = km.fit_predict(X)
            sil = None
            if len(X) <= 60_000:  # silhouette is O(n^2); cap the sample cost
                sample_idx = np.random.default_rng(42).choice(
                    len(X), size=min(8_000, len(X)), replace=False
                )
                sil = float(silhouette_score(X[sample_idx], labels[sample_idx]))
            return km, labels, sil

        if config.find_best_k:
            sweep = {}
            for k in range(2, 9):
                km, labels, sil = _fit(k)
                sweep[k] = (km, labels, sil)
                if sil is not None:
                    silhouette_by_k[str(k)] = round(sil, 4)
                if progress:
                    progress(f"[kmeans] k={k} inertia={km.inertia_:.0f} silhouette={sil}")
            best_k = max(sweep, key=lambda k: sweep[k][2] or float("-inf"))
            kmeans, labels, silhouette = sweep[best_k]
            if progress:
                progress(f"[kmeans] best k={best_k}")
        else:
            kmeans, labels, silhouette = _fit(config.k)
        kmeans_seconds = time.perf_counter() - t0

        df_work = df_clean.copy()
        df_work["cluster"] = labels.astype(int)
        inertia = float(kmeans.inertia_)

        # ---- Stage: PCA ----------------------------------------------------
        t0 = time.perf_counter()
        pca = PCA(n_components=2, random_state=42)
        coords = pca.fit_transform(X)
        pca_seconds = time.perf_counter() - t0

        # ---- Stage: aggregate ----------------------------------------------
        t0 = time.perf_counter()
        decades, cluster_profiles = self._aggregate(df_work, feature_cols)
        agg_seconds = time.perf_counter() - t0

        # ---- Benchmark: vectorized pandas vs pure-python loop ---------------
        bench = self._benchmark(df_work, feature_cols)

        if progress:
            progress(
                f"[aggregate] decades={len(decades)} profiles={len(cluster_profiles)} "
                f"in {agg_seconds:.2f}s"
            )

        return {
            "engine": self.name,
            "rows_ingested": int(len(df)),
            "rows_clean": int(len(df_clean)),
            "timings": {
                "clean": clean_seconds,
                "assemble": assemble_seconds,
                "kmeans": kmeans_seconds,
                "pca": pca_seconds,
                "aggregate": agg_seconds,
            },
            "inertia": inertia,
            "silhouette": silhouette,
            "best_k": best_k,
            "silhouette_by_k": silhouette_by_k,
            "clusters": cluster_profiles,
            "decades": decades,
            "pca_sample": self._pca_sample(df_work, coords),
            "feature_trends": self._feature_trends(df_work, feature_cols),
            "benchmark": bench,
            "track_frame": df_work,
            "config_used": config.model_dump(),
        }

    # ------------------------------------------------------------------ #
    def _aggregate(
        self, df: pd.DataFrame, feature_cols: list[str]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        counts = df.groupby(["decade", "cluster"]).size().unstack(fill_value=0)
        counts = counts.reindex(sorted(counts.index))
        decades: list[dict[str, Any]] = []
        for decade, row in counts.iterrows():
            total = int(row.sum())
            shares = {str(c): round(100.0 * row[c] / total, 2) for c in row.index if total}
            decades.append({"decade": int(decade), "total": total, "shares": shares})

        grouped = df.groupby("cluster")
        profiles: list[dict[str, Any]] = []
        for cluster_id, g in grouped:
            means = {c: round(float(g[c].mean()), 4) for c in feature_cols}
            profiles.append(
                {
                    "cluster": int(cluster_id),
                    "size": int(len(g)),
                    "share_pct": round(100.0 * len(g) / len(df), 2),
                    "label": _label_for(int(cluster_id)),
                    "means": means,
                }
            )
        profiles.sort(key=lambda pr: pr["cluster"])
        return decades, profiles

    def _pca_sample(
        self, df: pd.DataFrame, coords: np.ndarray, cap: int = 5_000
    ) -> list[dict[str, Any]]:
        n = len(df)
        if n > cap:
            idx = np.random.default_rng(42).choice(n, size=cap, replace=False)
        else:
            idx = np.arange(n)
        sub = df.iloc[idx]
        return [
            {
                "x": round(float(coords[i, 0]), 4),
                "y": round(float(coords[i, 1]), 4),
                "cluster": int(r["cluster"]),
                "name": str(r.get("name", ""))[:60],
                "artists": str(r.get("artists", ""))[:40],
                "year": int(r["year"]) if pd.notna(r.get("year")) else None,
            }
            for i, (_, r) in enumerate(sub.iterrows())
        ]

    def _feature_trends(
        self, df: pd.DataFrame, feature_cols: list[str]
    ) -> dict[str, dict[str, float]]:
        trends: dict[str, dict[str, float]] = {}
        for c in feature_cols:
            by_decade = df.groupby("decade")[c].mean()
            trends[c] = {str(int(d)): round(float(v), 4) for d, v in by_decade.items()}
        return trends

    def _benchmark(self, df: pd.DataFrame, feature_cols: list[str]) -> dict[str, Any]:
        cols = ["decade", *feature_cols[:4]]
        small = df[cols]

        t0 = time.perf_counter()
        vectorized = small.groupby("decade").mean()
        vec_seconds = time.perf_counter() - t0

        pairs = list(zip(small["decade"].tolist(), small[feature_cols[:4]].itertuples(index=False, name=None)))
        t0 = time.perf_counter()
        _pure_python_groupby_mean(pairs)
        loop_seconds = time.perf_counter() - t0

        speedup = loop_seconds / vec_seconds if vec_seconds > 0 else 0.0
        return {
            "label_a": "Vectorized pandas (groupby engine)",
            "label_b": "Pure-Python row loop",
            "seconds_a": round(vec_seconds, 4),
            "seconds_b": round(loop_seconds, 4),
            "speedup": round(speedup, 2),
            "note": (
                "Single-node analogue of the Spark-vs-Pandas benchmark: the vectorized "
                "engine replaces the naive per-row loop, the same way Spark parallelizes it."
            ),
        }
