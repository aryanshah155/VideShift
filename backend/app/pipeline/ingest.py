"""Ingestion: locate the Spotify tracks CSV and read it into a DataFrame.

Columnar Parquet is read directly by the engines; CSV is parsed here once
with the same fault-tolerant settings used in the Colab transcript.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from ..config import get_settings
from ..schema import ALL_COLS


def dataset_path() -> Path:
    """Return the configured CSV path (existence not guaranteed)."""
    return get_settings().csv_path


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


def dataset_status() -> dict:
    """Report whether the dataset is present and usable."""
    path = dataset_path()
    if not path.exists():
        parent = path.parent
        hints = [p.name for p in parent.glob("*.csv")] if parent.exists() else []
        msg = (
            f"Place 'tracks_features.csv' in {parent} and restart the pipeline. "
            + (f"Found other CSVs: {hints}" if hints else "Folder is empty.")
        )
        return {"found": False, "path": str(path), "size_mb": None, "message": msg}
    size_mb = path.stat().st_size / (1024 * 1024)
    return {
        "found": True,
        "path": str(path),
        "size_mb": round(size_mb, 1),
        "message": "Dataset detected. Ready to run the pipeline.",
    }
