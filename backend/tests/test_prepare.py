"""Tests for the data preparation stage."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.pipeline.prepare import clean_dataframe, to_feature_matrix
from app.schemas import RunConfig


def test_clean_casts_decimal_years(sample_df):
    df = sample_df.copy()
    df["year"] = (df["year"] + 0.0).astype(str) + ".0"  # "1998.0" strings
    cfg = RunConfig().normalized()
    out = clean_dataframe(df, cfg)
    assert out["year"].dtype.kind == "i"
    assert (out["year"] >= 1960).all() and (out["year"] <= 2023).all()
    assert "decade" in out.columns
    assert (out["decade"] % 10 == 0).all()


def test_clean_drops_malformed_and_null_rows(sample_df):
    df = sample_df.copy()
    df["energy"] = df["energy"].astype(object)  # simulate malformed CSV strings
    df["year"] = df["year"].astype(object)
    df.loc[0, "energy"] = "not-a-number"
    df.loc[1, "year"] = "garbage"
    cfg = RunConfig().normalized()
    out = clean_dataframe(df, cfg)
    assert len(out) == len(df) - 2


def test_clean_respects_year_range(sample_df):
    cfg = RunConfig(year_from=1980, year_to=1999).normalized()
    out = clean_dataframe(sample_df, cfg)
    assert out["year"].between(1980, 1999).all()
    assert set(out["decade"].unique()).issubset({1980, 1990})


def test_feature_matrix_standardized(sample_df):
    cfg = RunConfig().normalized()
    df = clean_dataframe(sample_df, cfg)
    X = to_feature_matrix(df, cfg.features)
    assert abs(X.mean()) < 1e-9
    assert abs(X.std(ddof=0).mean() - 1.0) < 1e-9


def test_missing_year_column_raises(sample_df):
    df = sample_df.drop(columns=["year"])
    with pytest.raises(ValueError, match="year"):
        clean_dataframe(df, RunConfig().normalized())
