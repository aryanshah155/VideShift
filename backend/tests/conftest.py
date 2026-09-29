"""Shared pytest fixtures."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_df() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 400
    eras = rng.integers(1960, 2024, n)
    # Make clusters noticeable: acoustic in the 60s, electronic later
    acoustic = np.clip(1 - (eras - 1960) / 70, 0.05, 0.95)
    return pd.DataFrame(
        {
            "id": [f"t{i}" for i in range(n)],
            "name": [f"Track {i}" for i in range(n)],
            "artists": [f"Artist {i % 23}" for i in range(n)],
            "year": eras,
            "release_date": ["2000-01-01"] * n,
            "danceability": rng.uniform(0, 1, n),
            "energy": np.clip(1 - acoustic + rng.normal(0, 0.1, n), 0, 1),
            "valence": rng.uniform(0, 1, n),
            "tempo": rng.uniform(60, 200, n),
            "acousticness": np.clip(acoustic + rng.normal(0, 0.1, n), 0, 1),
            "instrumentalness": rng.uniform(0, 1, n),
            "loudness": rng.uniform(-60, 0, n),
            "speechiness": rng.uniform(0, 1, n),
        }
    )
