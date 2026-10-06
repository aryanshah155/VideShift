"""Exploratory data analysis + statistics (Exp.8 data analysis, CO6-LO6).

The "understand the data before you model it" half of the lab manual:

* descriptive statistics per feature (mean/std/quartiles/skew/kurtosis)
* a Pearson correlation matrix over the acoustic features
* IQR-based univariate outlier counts
* Isolation Forest multivariate anomaly count
* a missing-value report

Everything is emitted as plain JSON so the React dashboards can draw the
correlation heatmap and outlier bars directly.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd

EXPERIMENT = "Exp.8 / CO6-LO6"
TITLE = "Statistical computing, correlation analysis & data visualization"


def _f(value: Any, nd: int = 6) -> float | None:
    """Coerce to a finite JSON-friendly float."""
    if value is None:
        return None
    try:
        out = float(value)
    except Exception:
        return None
    if not np.isfinite(out):
        return None
    return round(out, nd)


def run_eda(df: pd.DataFrame, feature_cols: list[str], sample_cap: int = 20_000) -> dict[str, Any]:
    t0 = time.perf_counter()
    cols = [c for c in feature_cols if c in df.columns]
    if not cols:
        return {"experiment": EXPERIMENT, "error": "no feature columns present"}

    X = df[cols].apply(pd.to_numeric, errors="coerce")

    # ---- descriptive statistics ------------------------------------------ #
    stats: dict[str, dict[str, Any]] = {}
    for c in cols:
        s = X[c].dropna()
        if s.empty:
            stats[c] = {}
            continue
        stats[c] = {
            "count": int(s.count()),
            "mean": _f(s.mean()),
            "std": _f(s.std(ddof=0)),
            "min": _f(s.min()),
            "q1": _f(s.quantile(0.25)),
            "median": _f(s.median()),
            "q3": _f(s.quantile(0.75)),
            "max": _f(s.max()),
            "skew": _f(s.skew()),
            "kurtosis": _f(s.kurtosis()),
            "range": _f(s.max() - s.min()),
        }

    # ---- Pearson correlation matrix -------------------------------------- #
    corr_df = X.corr(method="pearson")
    correlation: dict[str, dict[str, float | None]] = {
        a: {b: _f(corr_df.loc[a, b]) for b in cols} for a in cols
    }
    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            r = correlation[a][b]
            if r is not None:
                pairs.append({"a": a, "b": b, "r": r, "abs_r": abs(r)})
    pairs.sort(key=lambda p: -p["abs_r"])

    # ---- IQR outliers ----------------------------------------------------- #
    outliers: dict[str, dict[str, Any]] = {}
    total_outlier_flags = 0
    for c in cols:
        s = X[c].dropna()
        if s.empty:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = float(q3 - q1)
        lo, hi = float(q1) - 1.5 * iqr, float(q3) + 1.5 * iqr
        flags = int(((s < lo) | (s > hi)).sum())
        total_outlier_flags += flags
        outliers[c] = {
            "lower": _f(lo),
            "upper": _f(hi),
            "iqr": _f(iqr),
            "count": flags,
            "pct": _f(100.0 * flags / max(1, len(s)), 3),
        }

    # ---- multivariate anomalies (Isolation Forest) ------------------------ #
    n = len(X)
    sample_n = min(sample_cap, n)
    rng = np.random.default_rng(42)
    idx = (
        rng.choice(n, size=sample_n, replace=False)
        if n > sample_n
        else np.arange(n)
    )
    anomaly: dict[str, Any] = {
        "method": "IsolationForest(contamination=0.02, random_state=42)",
        "sampled": int(sample_n),
        "total": int(n),
        "contamination": 0.02,
        "count": None,
    }
    try:
        from sklearn.ensemble import IsolationForest

        matrix = X.iloc[idx].to_numpy(dtype=float)
        matrix = np.nan_to_num(matrix, nan=0.0)
        preds = IsolationForest(
            contamination=0.02, random_state=42, n_jobs=1
        ).fit_predict(matrix)
        anomaly["count"] = int((preds == -1).sum())
        anomaly["pct"] = _f(100.0 * anomaly["count"] / max(1, sample_n), 3)
    except Exception as exc:  # noqa: BLE001
        anomaly["error"] = f"{type(exc).__name__}: {exc}"

    missing = {c: _f(100.0 * float(df[c].isna().mean()), 3) for c in cols}

    return {
        "experiment": EXPERIMENT,
        "title": TITLE,
        "seconds": round(time.perf_counter() - t0, 3),
        "rows": int(len(df)),
        "feature_columns": cols,
        "stats": stats,
        "correlation": correlation,
        "strongest_pairs": pairs[:8],
        "outliers": outliers,
        "outlier_flags_total": total_outlier_flags,
        "anomaly": anomaly,
        "missing_pct": missing,
        "decade_counts": {
            str(int(k)): int(v)
            for k, v in df.groupby("decade").size().items()
        }
        if "decade" in df.columns
        else {},
    }
