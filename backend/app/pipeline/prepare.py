"""Shared data preparation used by both engines.

Mirrors the Colab transcript's Section 3/4 (cleaning + vector assembly),
including the hard-won fixes: safe double->int year casting, ANSI-off
fault-tolerant casts, and explicit feature casting with dropna.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..schema import FEATURE_COLS, META_COLS
from ..schemas import RunConfig


def clean_dataframe(df: pd.DataFrame, config: RunConfig, progress=None) -> pd.DataFrame:
    """Select meta + feature columns, safe-cast, filter years, add decade."""
    if progress:
        progress(f"selecting {len(META_COLS) + len(FEATURE_COLS)} of {len(df.columns)} columns")

    cols = [c for c in META_COLS + config.features if c in df.columns]
    df = df.loc[:, cols].copy()

    # Fault-tolerant casts (malformed strings become NaN instead of raising).
    for c in config.features:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "year" in df.columns:
        # The transcript fix: cast through float to parse "2004.0" style years.
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Float64")
        df = df.dropna(subset=["year"])
        df["year"] = df["year"].astype(int)
        df = df[(df["year"] >= config.year_from) & (df["year"] <= config.year_to)]
    else:
        raise ValueError("Dataset is missing the 'year' column required for vibe-shift analysis")

    df["decade"] = (df["year"] // 10 * 10).astype(int)

    before = len(df)
    df = df.dropna(subset=config.features)
    if progress:
        progress(f"cleaned {before:,} -> {len(df):,} rows after casting + dropna")

    # Drop exact duplicate track ids, keep the first occurrence.
    if "id" in df.columns:
        before = len(df)
        df = df.drop_duplicates(subset=["id"], keep="first")
        if progress:
            progress(f"removed {before - len(df):,} duplicate track ids")

    return df.reset_index(drop=True)


def sample_dataframe(df: pd.DataFrame, config: RunConfig, progress=None) -> pd.DataFrame:
    """Optional random row sampling controlled by the run config."""
    if config.sample_fraction < 1.0 and len(df) > 0:
        frac = float(config.sample_fraction)
        df = df.sample(frac=frac, random_state=42).reset_index(drop=True)
        if progress:
            progress(f"sampling {frac:.0%} of rows -> {len(df):,} rows")
    return df


def to_feature_matrix(df: pd.DataFrame, feature_cols: list[str]) -> np.ndarray:
    """Assemble + standardize the feature matrix (VectorAssembler + StandardScaler).

    Uses ddof=0 (population std) to match PySpark's StandardScaler exactly.
    """
    X = df[feature_cols].to_numpy(dtype=np.float64)
    X = np.nan_to_num(X, nan=0.0)
    mean = X.mean(axis=0)
    std = X.std(axis=0, ddof=0)
    std[std == 0.0] = 1.0
    return (X - mean) / std
