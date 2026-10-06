"""Ingestion: locate the Spotify tracks CSV and read it into a DataFrame.

Columnar Parquet is read directly by the engines; CSV is parsed here once
with the same fault-tolerant settings used in the Colab transcript.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from ..config import get_settings
from ..schema import ALL_COLS


def dataset_path() -> Path:
    """Return the configured CSV path (existence not guaranteed)."""
    return get_settings().csv_path


# --------------------------------------------------------------------------- #
# Dataset profile (row/column count + the *actual* min/max year)
# --------------------------------------------------------------------------- #
# The Dashboard's "Year from / Year to" inputs get their bounds from here, so
# the run config can never ask for a window the dataset cannot satisfy.
# The scan is cached (keyed on file size + mtime) because re-reading a 1.2M row
# CSV on every dashboard refresh would be wasteful.


# Bump when the shape of the cached profile changes, so older cache entries are
# rescanned instead of being served with missing fields.
_PROFILE_VERSION = 3


def _meta_cache_path() -> Path:
    d = get_settings().data_dir / "_store"
    d.mkdir(parents=True, exist_ok=True)
    return d / "dataset_meta.json"


def _empty_profile() -> dict:
    return {
        "rows": None,
        "columns": None,
        "year_min": None,
        "year_max": None,
        "year_p01": None,
        "year_p99": None,
        "year_raw_min": None,
        "year_invalid_rows": None,
        "decade_counts": {},
    }


def _scan_dataset_profile(path: Path) -> dict:
    """Read only what we need: header width, row count, and the year column.

    The Kaggle Spotify dump encodes an unknown release year as ``0``, so the
    reported ``year_min``/``year_max`` ignore non-positive years; the raw minimum
    and the count of invalid rows are reported separately so nothing is hidden.
    """
    profile = _empty_profile()

    try:  # header only - cheap way to count columns
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            header = fh.readline()
        if header:
            profile["columns"] = len([c for c in header.strip().split(",") if c.strip()])
    except Exception:
        pass

    years = None
    parquet = path.with_suffix(".parquet")
    try:  # prefer the fresh Parquet cache when it exists
        if parquet.exists() and parquet.stat().st_mtime >= path.stat().st_mtime:
            years = pd.read_parquet(parquet, columns=["year"])["year"]
    except Exception:
        years = None
    if years is None:
        try:  # stream just the year column (still avoids loading 20 columns)
            years = pd.read_csv(path, usecols=["year"], low_memory=False)["year"]
        except Exception:
            years = None

    if years is None or not len(years):
        return profile

    profile["rows"] = int(len(years))
    # Same safe cast used by the pipeline: "2004.0" strings -> 2004.
    numeric = pd.to_numeric(years, errors="coerce")
    valid = numeric[numeric > 0].dropna()
    profile["year_invalid_rows"] = int(len(numeric) - len(valid))
    if not len(valid):
        return profile

    profile["year_raw_min"] = int(numeric.min()) if numeric.notna().any() else None
    profile["year_min"] = int(valid.min())
    profile["year_max"] = int(valid.max())
    profile["year_p01"] = int(valid.quantile(0.01))
    profile["year_p99"] = int(valid.quantile(0.99))

    decades = (valid // 10 * 10).astype(int).value_counts().sort_index()
    profile["decade_counts"] = {str(int(d)): int(c) for d, c in decades.items()}
    return profile


def dataset_profile(path: Path | None = None, refresh: bool = False) -> dict:
    """Row count, column count and real min/max year for the dataset."""
    path = path or dataset_path()
    if not path.exists():
        return _empty_profile()

    cache = _meta_cache_path()
    stat = path.stat()
    key = {
        "v": _PROFILE_VERSION,
        "name": path.name,
        "size": stat.st_size,
        "mtime": int(stat.st_mtime),
    }
    if not refresh and cache.exists():
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            if cached.get("_key") == key and cached.get("profile"):
                return cached["profile"]
        except Exception:
            pass

    profile = _scan_dataset_profile(path)
    try:
        cache.write_text(json.dumps({"_key": key, "profile": profile}, indent=1), encoding="utf-8")
    except Exception:
        pass
    return profile


def read_csv_safe(path: Path) -> pd.DataFrame:
    """Fault-tolerant CSV read: quote/escape handling, malformed rows -> NaN."""
    return pd.read_csv(
        path,
        low_memory=False,
        quoting=3,  # QUOTE_NONE handled per-field; pandas still honors quotes
        on_bad_lines="skip",
    )


def load_dataframe(progress_cb=None) -> tuple[pd.DataFrame, float, int]:
    """Load the dataset as a pandas DataFrame.

    Prefers a cached Parquet conversion for speed; falls back to CSV.
    Returns (df, seconds, rows).
    """
    settings = get_settings()
    path = dataset_path()
    parquet = path.with_suffix(".parquet")
    t0 = time.perf_counter()

    if parquet.exists() and parquet.stat().st_mtime >= path.stat().st_mtime:
        df = pd.read_parquet(parquet)
        source = "parquet-cache"
    else:
        df = read_csv_safe(path)
        source = "csv"

    seconds = time.perf_counter() - t0
    rows = int(len(df))
    if progress_cb:
        progress_cb(f"read {rows:,} rows from {source} in {seconds:.2f}s")
    return df, seconds, rows


def ensure_parquet_cache(df: pd.DataFrame) -> Path:
    """Write a Parquet cache of the ingested frame for faster Spark runs."""
    settings = get_settings()
    parquet = settings.csv_path.with_suffix(".parquet")
    df[ALL_COLS].to_parquet(parquet, index=False)
    return parquet


def dataset_status(refresh: bool = False) -> dict:
    """Report whether the dataset is present, its size, and its real year range."""
    path = dataset_path()
    if not path.exists():
        parent = path.parent
        hints = [p.name for p in parent.glob("*.csv")] if parent.exists() else []
        msg = (
            f"Place 'tracks_features.csv' in {parent} and restart the pipeline. "
            + (f"Found other CSVs: {hints}" if hints else "Folder is empty.")
        )
        return {"found": False, "path": str(path), "size_mb": None, "message": msg, **_empty_profile()}
    size_mb = path.stat().st_size / (1024 * 1024)
    profile = dataset_profile(path, refresh=refresh)
    span = ""
    if profile.get("year_min") is not None:
        span = (
            f" Valid years {profile['year_min']}-{profile['year_max']}"
            f" (99% inside {profile.get('year_p01')}-{profile.get('year_p99')})."
        )
    return {
        "found": True,
        "path": str(path),
        "size_mb": round(size_mb, 1),
        "message": f"Dataset detected. Ready to run the pipeline.{span}",
        **profile,
    }
