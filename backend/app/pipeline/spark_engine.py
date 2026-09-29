"""PySpark MLlib engine — the Colab pipeline, stage-instrumented.

Used automatically when pyspark is importable and the JVM is compatible;
otherwise the registry falls back to the pandas engine.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from ..schema import ALL_COLS, FEATURE_COLS
from ..schemas import RunConfig
from .base import stage_progress
from .prepare import clean_dataframe, sample_dataframe


class SparkEngine:
    name = "spark"

    def run(
        self,
        df: Any,
        config: RunConfig,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        import pyspark.sql.functions as F
        from pyspark.ml.clustering import KMeans
        from pyspark.ml.evaluation import ClusteringEvaluator
        from pyspark.ml.feature import PCA, StandardScaler, VectorAssembler
        from pyspark.sql import SparkSession

        p = stage_progress("prepare", progress)

        # ---- Stage: clean (shared with the pandas engine) ------------------
        t0 = time.perf_counter()
        df_clean = clean_dataframe(df, config, progress=p)
        df_clean = sample_dataframe(df_clean, config, progress=p)
        clean_seconds = time.perf_counter() - t0

        # ---- Spark session --------------------------------------------------
        spark = (
            SparkSession.builder.appName("VibeShift")
            .config("spark.sql.ansi.enabled", "false")
            .config("spark.execution.arrow.pyspark.enabled", "true")
            .getOrCreate()
        )
        sdf = spark.createDataFrame(df_clean[ALL_COLS])
        sdf.cache()
        sdf.count()

        # ---- Stage: VectorAssembler + StandardScaler ------------------------
        t0 = time.perf_counter()
        assembler = VectorAssembler(inputCols=config.features, outputCol="raw_features")
        scaled_df = assembler.transform(sdf)
        scaler_model = StandardScaler(
            inputCol="raw_features",
            outputCol="scaled_features",
            withMean=True,
            withStd=True,
        ).fit(scaled_df)
        scaled_df = scaler_model.transform(scaled_df).cache()
        scaled_df.count()
        assemble_seconds = time.perf_counter() - t0
        if progress:
            progress(f"[assemble] VectorAssembler + StandardScaler done in {assemble_seconds:.2f}s")

        def _fit_k(k: int):
            km = KMeans(k=k, seed=42, featuresCol="scaled_features", predictionCol="cluster")
            model = km.fit(scaled_df)
            out = model.transform(scaled_df).cache()
            out.count()
            return model, out

        # ---- Stage: KMeans (optional best-k sweep) --------------------------
        t0 = time.perf_counter()
        best_k = None
        silhouette_by_k: dict[str, float] = {}
        evaluator = ClusteringEvaluator(
            featuresCol="scaled_features", predictionCol="cluster", metricName="silhouette"
        )

        if config.find_best_k:
            sweep: dict[int, tuple[Any, Any, float]] = {}
            for k in range(2, 9):
                model, out = _fit_k(k)
                sil = float(evaluator.evaluate(out))
                sweep[k] = (model, out, sil)
                silhouette_by_k[str(k)] = round(sil, 4)
                if progress:
                    progress(f"[kmeans] k={k} trainingCost={model.summary.trainingCost:.0f} silhouette={sil:.4f}")
            best_k = max(sweep, key=lambda k: sweep[k][2])
            kmeans_model, df_clustered, silhouette = sweep[best_k]
            if progress:
                progress(f"[kmeans] best k={best_k}")
        else:
            kmeans_model, df_clustered = _fit_k(config.k)
            silhouette = float(evaluator.evaluate(df_clustered))
        kmeans_seconds = time.perf_counter() - t0
        inertia = float(kmeans_model.summary.trainingCost)

        # ---- Stage: PCA ------------------------------------------------------
        t0 = time.perf_counter()
        pca_model = PCA(k=2, inputCol="scaled_features", outputCol="pca_features").fit(df_clustered)
        df_pca = pca_model.transform(df_clustered).cache()
        df_pca.count()
        pca_seconds = time.perf_counter() - t0
        if progress:
            progress(f"[pca] explained variance={pca_model.explainedVariance.values.round(4)}")

        # ---- Stage: aggregate decade x cluster -------------------------------
        t0 = time.perf_counter()
        decades = self._decade_shares(df_pca, F)
        clusters = self._cluster_profiles(df_clustered, config.features, F)
        agg_seconds = time.perf_counter() - t0

        # ---- Track frame + PCA sample (small collects, Arrow-backed) ---------
        track_frame = df_clustered.select("id", "name", "artists", "year", "decade", "cluster").toPandas()
        pca_sample = self._pca_sample(spark, df_pca, F)

        # ---- Benchmark: Spark vs pandas on the same aggregation --------------
        bench = self._benchmark(spark, df_pca, F, len(track_frame))

        feature_trends = self._feature_trends(df_clustered, config.features, F)

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
            "clusters": clusters,
            "decades": decades,
            "pca_sample": pca_sample,
            "feature_trends": feature_trends,
            "benchmark": bench,
            "track_frame": track_frame,
            "config_used": config.model_dump(),
        }

    # ------------------------------------------------------------------ #
    def _decade_shares(self, df_pca: Any, F: Any) -> list[dict[str, Any]]:
        counts = (
            df_pca.groupBy("decade")
            .pivot("cluster")
            .count()
            .fillna(0)
            .orderBy("decade")
            .toPandas()
            .set_index("decade")
        )
        decades: list[dict[str, Any]] = []
        for decade, row in counts.iterrows():
            total = int(row.sum())
            shares = {str(int(c)): round(100.0 * row[c] / total, 2) for c in row.index if total}
            decades.append({"decade": int(decade), "total": total, "shares": shares})
        return decades

    def _cluster_profiles(
        self, df_clustered: Any, feature_cols: list[str], F: Any
    ) -> list[dict[str, Any]]:
        from .pandas_engine import _label_for

        sizes = df_clustered.groupBy("cluster").count().toPandas().set_index("cluster")["count"]
        means = df_clustered.groupBy("cluster").mean(*feature_cols).toPandas().set_index("cluster")
        total = int(sizes.sum())
        profiles: list[dict[str, Any]] = []
        for cluster_id in sorted(sizes.index):
            row = means.loc[cluster_id]
            clean_means = {
                c: round(float(row["avg(" + c + ")"]), 4) for c in feature_cols
            }
            profiles.append(
                {
                    "cluster": int(cluster_id),
                    "size": int(sizes[cluster_id]),
                    "share_pct": round(100.0 * int(sizes[cluster_id]) / total, 2),
                    "label": _label_for(int(cluster_id)),
                    "means": clean_means,
                }
            )
        return profiles

    def _pca_sample(self, spark: Any, df_pca: Any, F: Any, cap: int = 5_000) -> list[dict[str, Any]]:
        sampled = df_pca.orderBy(F.rand(seed=42)).limit(cap)
        rows = sampled.select(
            "pca_features", "cluster", "name", "artists", "year"
        ).toPandas()
        out: list[dict[str, Any]] = []
        for _, r in rows.iterrows():
            vec = r["pca_features"]
            out.append(
                {
                    "x": round(float(vec[0]), 4),
                    "y": round(float(vec[1]), 4),
                    "cluster": int(r["cluster"]),
                    "name": str(r.get("name", ""))[:60],
                    "artists": str(r.get("artists", ""))[:40],
                    "year": int(r["year"]) if r.get("year") is not None else None,
                }
            )
        return out

    def _feature_trends(
        self, df_clustered: Any, feature_cols: list[str], F: Any
    ) -> dict[str, dict[str, float]]:
        trends: dict[str, dict[str, float]] = {}
        for c in feature_cols:
            rows = (
                df_clustered.groupBy("decade")
                .agg(F.avg(c).alias("v"))
                .orderBy("decade")
                .toPandas()
            )
            trends[c] = {str(int(r["decade"])): round(float(r["v"]), 4) for _, r in rows.iterrows()}
        return trends

    def _benchmark(self, spark: Any, df_pca: Any, F: Any, n_rows: int) -> dict[str, Any]:
        """Time the decade x cluster aggregation in Spark, then in pandas."""
        t0 = time.perf_counter()
        (
            df_pca.groupBy("decade")
            .pivot("cluster")
            .count()
            .fillna(0)
            .orderBy("decade")
            .toPandas()
        )
        spark_seconds = time.perf_counter() - t0

        import pandas as pd

        pdf = df_pca.select("decade", "cluster").toPandas()
        t0 = time.perf_counter()
        _ = pd.crosstab(pdf["decade"], pdf["cluster"])
        pandas_seconds = time.perf_counter() - t0

        speedup = pandas_seconds / spark_seconds if spark_seconds > 0 else 0.0
        return {
            "label_a": "PySpark distributed aggregation",
            "label_b": "Single-node pandas crosstab",
            "seconds_a": round(spark_seconds, 4),
            "seconds_b": round(pandas_seconds, 4),
            "speedup": round(speedup, 2),
            "note": f"Same decade x cluster pivot over {n_rows:,} rows: Spark vs pandas.",
        }
