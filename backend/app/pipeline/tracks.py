"""Per-run track store backed by Parquet + pyarrow dataset filters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pyarrow_ds  # noqa: F401  (ensures parquet support is present)
import pyarrow.parquet as pq

from ..config import get_settings


def _runs_dir() -> Path:
    d = get_settings().data_dir / "_runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_tracks(run_id: str, df: Any) -> Path:
    path = _runs_dir() / run_id / "tracks.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [c for c in ["id", "name", "artists", "year", "decade", "cluster"] if c in df.columns]
    df[cols].to_parquet(path, index=False)
    return path


def query_tracks(
    run_id: str,
    search: str | None = None,
    cluster: int | None = None,
    decade: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Search + filter + paginate over one run's track assignments."""
    path = _runs_dir() / run_id / "tracks.parquet"
    if not path.exists():
        return {"total": 0, "page": page, "page_size": page_size, "tracks": []}

    import pandas as pd

    df = pd.read_parquet(path)

    if search:
        needle = search.lower()
        mask = (
            df["name"].astype(str).str.lower().str.contains(needle, na=False)
            | df["artists"].astype(str).str.lower().str.contains(needle, na=False)
        )
        df = df[mask]
    if cluster is not None:
        df = df[df["cluster"] == cluster]
    if decade is not None:
        df = df[df["decade"] == decade]

    total = int(len(df))
    page = max(1, page)
    start = (page - 1) * page_size
    chunk = df.iloc[start : start + page_size]

    tracks = [
        {
            "id": r["id"],
            "name": str(r["name"])[:80],
            "artists": str(r["artists"])[:60],
            "year": int(r["year"]) if pd.notna(r["year"]) else None,
            "decade": int(r["decade"]) if pd.notna(r["decade"]) else None,
            "cluster": int(r["cluster"]) if pd.notna(r["cluster"]) else None,
        }
        for _, r in chunk.iterrows()
    ]
    return {"total": total, "page": page, "page_size": page_size, "tracks": tracks}


def delete_run_artifacts(run_id: str) -> None:
    import shutil

    shutil.rmtree(_runs_dir() / run_id, ignore_errors=True)
