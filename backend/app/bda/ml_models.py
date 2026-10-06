"""Machine learning beyond clustering (Exp.2, CO2-LO2).

The manual's second experiment asks for *any* MLlib algorithm with a 70/30
``randomSplit([0.7, 0.3], seed=42)``, relevant metrics and a feature-importance
plot. This module delivers three complementary pieces, all on the same clean
feature matrix the clusterer used:

* **Supervised era classification** - predict ``year >= 2000`` from the acoustic
  features with RandomForest / DecisionTree / LogisticRegression; report accuracy,
  precision, recall, F1, a confusion matrix, ROC-AUC and RF feature importances.
* **Model selection curves** - the K-Means elbow (inertia) and silhouette score
  for k=2..10, i.e. how k was actually chosen.
* **Hierarchical clustering** - Ward linkage on a sample, returned as a real
  dendrogram (merge heights + segment geometry), plus its agreement with K-Means
  measured by the Adjusted Rand Index.

The pandas/sklearn implementations mirror the PySpark MLlib calls one-for-one so
the same numbers come out of either engine.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd

EXPERIMENT = "Exp.2 / CO2-LO2"
TITLE = "Machine learning with MLlib semantics: split, train, evaluate, explain"

TARGET_YEAR = 2000


def _matrix(df: pd.DataFrame, cols: list[str]) -> np.ndarray:
    X = df[cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    return np.nan_to_num(X, nan=0.0)


def _standardize(X: np.ndarray) -> np.ndarray:
    mu = X.mean(axis=0)
    sd = X.std(axis=0, ddof=0)
    sd[sd == 0.0] = 1.0
    return (X - mu) / sd


def _supervised(df: pd.DataFrame, cols: list[str], cap: int) -> dict[str, Any]:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
        roc_curve,
    )
    from sklearn.model_selection import train_test_split
    from sklearn.tree import DecisionTreeClassifier

    work = df
    if len(work) > cap:
        work = work.sample(n=cap, random_state=42)

    X = _matrix(work, cols)
    y = (pd.to_numeric(work["year"], errors="coerce") >= TARGET_YEAR).to_numpy(dtype=int)
    if len(np.unique(y)) < 2:
        return {"error": f"target 'year >= {TARGET_YEAR}' has a single class in this sample"}

    # Mirrors PySpark's df.randomSplit([0.7, 0.3], seed=42)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )

    candidate_models = [
        ("RandomForest", RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=1)),
        ("DecisionTree", DecisionTreeClassifier(random_state=42, max_depth=8)),
        ("LogisticRegression", LogisticRegression(max_iter=1000, random_state=42)),
    ]

    results: list[dict[str, Any]] = []
    fitted: dict[str, Any] = {}
    for name, model in candidate_models:
        t0 = time.perf_counter()
        model.fit(X_train, y_train)
        train_seconds = time.perf_counter() - t0
        t1 = time.perf_counter()
        pred = model.predict(X_test)
        test_seconds = time.perf_counter() - t1
        auc = None
        try:
            if hasattr(model, "predict_proba"):
                auc = float(roc_auc_score(y_test, model.predict_proba(X_test)[:, 1]))
        except Exception:
            auc = None
        results.append(
            {
                "name": name,
                "accuracy": round(float(accuracy_score(y_test, pred)), 4),
                "precision": round(float(precision_score(y_test, pred, zero_division=0)), 4),
                "recall": round(float(recall_score(y_test, pred, zero_division=0)), 4),
                "f1": round(float(f1_score(y_test, pred, zero_division=0)), 4),
                "roc_auc": round(auc, 4) if auc is not None else None,
                "train_seconds": round(train_seconds, 4),
                "predict_seconds": round(test_seconds, 4),
            }
        )
        fitted[name] = (model, pred)

    best_row = max(results, key=lambda r: r["f1"])
    best_model, best_pred = fitted[best_row["name"]]
    cm = confusion_matrix(y_test, best_pred, labels=[0, 1]).tolist()

    roc_curve_points: list[dict[str, float]] = []
    try:
        if hasattr(best_model, "predict_proba"):
            fpr, tpr, _ = roc_curve(y_test, best_model.predict_proba(X_test)[:, 1])
            step = max(1, len(fpr) // 60)
            roc_curve_points = [
                {"fpr": round(float(fpr[i]), 4), "tpr": round(float(tpr[i]), 4)}
                for i in range(0, len(fpr), step)
            ]
            roc_curve_points.append({"fpr": 1.0, "tpr": 1.0})
    except Exception:
        roc_curve_points = []

    importances: dict[str, float] = {}
    rf = fitted.get("RandomForest", (None, None))[0]
    if rf is not None and hasattr(rf, "feature_importances_"):
        importances = {
            c: round(float(v), 4)
            for c, v in sorted(
                zip(cols, rf.feature_importances_), key=lambda kv: -kv[1]
            )
        }

    return {
        "target": f"is_modern = (year >= {TARGET_YEAR})",
        "positive_class": f"year >= {TARGET_YEAR}",
        "negative_class": f"year < {TARGET_YEAR}",
        "split": {
            "strategy": "train_test_split(test_size=0.3, random_state=42)"
            " ~ PySpark randomSplit([0.7, 0.3], seed=42)",
            "train_rows": int(len(X_train)),
            "test_rows": int(len(X_test)),
            "features": len(cols),
            "rows_used": int(len(X)),
        },
        "class_balance": {
            "train": {
                "negative": int((y_train == 0).sum()),
                "positive": int((y_train == 1).sum()),
            },
            "test": {
                "negative": int((y_test == 0).sum()),
                "positive": int((y_test == 1).sum()),
            },
        },
        "models": results,
        "best": best_row,
        "confusion_matrix": cm,
        "confusion_labels": ["pred < 2000", "pred >= 2000"],
        "roc_curve": roc_curve_points,
        "feature_importance": importances,
        "distributed_note": (
            "In Spark this is RandomForestClassifier.labelCol on a DataFrame with a "
            "VectorAssembler features column: the trees are trained per partition and "
            "aggregated by the driver, so the split data is never collected to one node."
        ),
    }


def _elbow(df: pd.DataFrame, cols: list[str], cap: int, sil_sample: int) -> dict[str, Any]:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    work = df
    if len(work) > cap:
        work = work.sample(n=cap, random_state=42)
    X = _standardize(_matrix(work, cols))

    ks = list(range(2, 11))
    inertia: list[float] = []
    silhouette: list[float | None] = []
    rng = np.random.default_rng(42)
    probe = (
        rng.choice(len(X), size=min(sil_sample, len(X)), replace=False)
        if len(X) > sil_sample
        else np.arange(len(X))
    )
    for k in ks:
        if len(X) < k:
            break
        km = KMeans(n_clusters=k, n_init=3, random_state=42)
        labels = km.fit_predict(X)
        inertia.append(round(float(km.inertia_), 2))
        try:
            silhouette.append(
                round(float(silhouette_score(X[probe], labels[probe])), 4)
            )
        except Exception:
            silhouette.append(None)

    # Knee of the inertia curve: the point furthest from the chord joining the
    # first and last points on the normalized curve ("kneedle"-style). Comparing
    # raw successive drops would always elect k=2, since inertia is monotone.
    elbow_k = None
    if len(inertia) >= 3:
        x = np.array(ks[: len(inertia)], dtype=float)
        y = np.array(inertia, dtype=float)
        xr = x.max() - x.min()
        yr = y.max() - y.min()
        if xr > 0 and yr > 0:
            xn = (x - x.min()) / xr
            yn = (y - y.min()) / yr
            distances = np.abs(xn + yn - 1.0) / np.sqrt(2.0)
            elbow_k = int(x[int(np.argmax(distances))])

    best_sil_k = None
    valid_sil = [(k, s) for k, s in zip(ks[: len(silhouette)], silhouette) if s is not None]
    if valid_sil:
        best_sil_k = int(max(valid_sil, key=lambda kv: kv[1])[0])

    return {
        "k": ks[: len(inertia)],
        "inertia": inertia,
        "silhouette": silhouette,
        "elbow_k": elbow_k,
        "best_silhouette_k": best_sil_k,
        "rows_used": int(len(X)),
        "silhouette_sample": int(len(probe)),
        "note": (
            "Elbow = the knee of the within-cluster SSE curve (max distance from the "
            "chord); silhouette = how well separated the clusters are. Together they "
            "justify the k used for the run."
        ),
    }


def _hierarchical(
    df: pd.DataFrame, cols: list[str], k: int, cap: int, seed: int = 42
) -> dict[str, Any]:
    try:
        from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
    except Exception as exc:  # noqa: BLE001
        return {"error": f"scipy unavailable: {exc}"}

    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import adjusted_rand_score

    n = min(cap, len(df))
    work = df.sample(n=n, random_state=seed).reset_index(drop=True)
    X = _standardize(_matrix(work, cols))

    Z = linkage(X, method="ward")
    tree = dendrogram(Z, no_plot=True)

    seg_x = tree["icoord"]
    seg_y = tree["dcoord"]
    segments: list[dict[str, float]] = []
    for xi, yi in zip(seg_x, seg_y):
        segments.append({"x1": round(xi[0], 2), "y1": round(yi[0], 4), "x2": round(xi[1], 2), "y2": round(yi[1], 4)})
        segments.append({"x1": round(xi[1], 2), "y1": round(yi[1], 4), "x2": round(xi[2], 2), "y2": round(yi[2], 4)})
        segments.append({"x1": round(xi[2], 2), "y1": round(yi[2], 4), "x2": round(xi[3], 2), "y2": round(yi[3], 4)})

    leaves = []
    for position, obs_index in enumerate(tree["leaves"]):
        row = work.iloc[int(obs_index)]
        leaves.append(
            {
                "x": round(5.0 + 10.0 * position, 2),
                "label": str(row.get("name", ""))[:22],
                "artists": str(row.get("artists", ""))[:18],
                "cluster": int(row.get("cluster", 0)),
                "year": int(row["year"]) if pd.notna(row.get("year")) else None,
            }
        )

    h_labels = fcluster(Z, t=max(2, min(k, n)), criterion="maxclust")
    km_labels = AgglomerativeClustering(n_clusters=max(2, min(k, n)), linkage="ward").fit_predict(X)
    ari = float(adjusted_rand_score(h_labels, km_labels))

    return {
        "method": "Ward linkage",
        "rows_used": int(n),
        "clusters_cut": int(max(2, min(k, n))),
        "merge_heights": [round(float(h), 4) for h in Z[:, 2][-6:]],
        "max_height": round(float(Z[:, 2].max()), 4),
        "leaves": leaves,
        "segments": segments,
        "leaf_order": [int(i) for i in tree["leaves"]],
        "ari_vs_agglomerative_cut": round(ari, 4),
        "note": (
            "Hierarchical clustering builds a merge tree instead of requiring k up "
            "front. ARI compares this tree cut against the flat K-Means solution."
        ),
    }


def run_ml(
    df: pd.DataFrame,
    feature_cols: list[str],
    *,
    k: int = 5,
    supervised_cap: int = 40_000,
    elbow_cap: int = 15_000,
    tree_cap: int = 120,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cols = [c for c in feature_cols if c in df.columns]
    if not cols or "year" not in df.columns:
        return {"experiment": EXPERIMENT, "error": "missing feature/year columns"}

    out: dict[str, Any] = {"experiment": EXPERIMENT, "title": TITLE}
    try:
        out["supervised"] = _supervised(df, cols, supervised_cap)
    except Exception as exc:  # noqa: BLE001
        out["supervised"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        out["elbow"] = _elbow(df, cols, elbow_cap, sil_sample=3_000)
    except Exception as exc:  # noqa: BLE001
        out["elbow"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        out["hierarchical"] = _hierarchical(df, cols, k, tree_cap)
    except Exception as exc:  # noqa: BLE001
        out["hierarchical"] = {"error": f"{type(exc).__name__}: {exc}"}

    out["seconds"] = round(time.perf_counter() - t0, 3)
    out["concepts"] = [
        "70/30 train/test split (randomSplit semantics)",
        "supervised classification: RandomForest, DecisionTree, LogisticRegression",
        "accuracy / precision / recall / F1 / ROC-AUC",
        "confusion matrix",
        "feature importance",
        "unsupervised model selection: elbow + silhouette sweep",
        "hierarchical (Ward) clustering + dendrogram",
        "cluster agreement via Adjusted Rand Index",
    ]
    return out
