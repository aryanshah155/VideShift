"""Stream data technique simulation (CO4-LO4).

The lab manual's fourth course outcome is *stream data techniques*. Streaming has
no meaning on a static CSV, so the corpus is replayed as an event stream:

* **Event time vs arrival time** - events are ordered by release year (event time)
  while the frame's row order plays the role of arrival order. Any event whose
  event time is behind the running maximum is counted as a late arrival, exactly
  what a watermark is built to absorb.
* **Tumbling windows** - fixed-size micro-batches with per-window feature means.
* **Sliding windows + EWMA** - a rolling view over the last N micro-batches.
* **Concept drift detection** - z-score of each new window mean against the
  previous rolling window, flagging distribution shifts (the "vibe shift"
  formalised as a change point rather than eyeballed on a heatmap).
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd

EXPERIMENT = "CO4-LO4"
TITLE = "Stream data techniques: micro-batches, sliding windows, concept drift"

DEFAULT_FEATURES = ["energy", "acousticness", "valence", "danceability"]


def run_streaming(
    df: pd.DataFrame,
    feature_cols: list[str],
    *,
    batch_size: int | None = None,
    target_batches: int = 60,
    window: int = 3,
    drift_z: float = 2.5,
    max_windows: int = 40,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cols = [c for c in feature_cols if c in df.columns]
    if not cols or "year" not in df.columns:
        return {"experiment": EXPERIMENT, "error": "missing year/feature columns"}

    stream_cols = [c for c in DEFAULT_FEATURES if c in cols] or cols[:3]

    events = df[["year", *stream_cols]].copy()
    events["year"] = pd.to_numeric(events["year"], errors="coerce")
    events = events.dropna(subset=["year"])

    # ---- arrival-order lateness (watermark) ----------------------------- #
    event_year = events["year"].to_numpy(dtype=float)
    running_max = np.maximum.accumulate(event_year)
    late_mask = np.zeros(len(events), dtype=bool)
    if len(events) > 1:
        late_mask[1:] = event_year[1:] < running_max[:-1]
    late_count = int(late_mask.sum())
    lateness_years = np.where(late_mask, running_max - event_year, 0.0)

    # ---- event-time ordered stream, tumbling micro-batches --------------- #
    ordered = events.sort_values("year", kind="mergesort").reset_index(drop=True)
    n_events = len(ordered)
    # Adaptive micro-batch size: aim for ~60 windows so each one covers roughly a
    # single release year on a 1M-row corpus, which keeps the drift test meaningful.
    if not batch_size or batch_size < 50:
        batch_size = max(200, int(np.ceil(n_events / target_batches))) if n_events else 200
    n_batches = int(np.ceil(n_events / batch_size)) if n_events else 0

    packed_cols = [ordered[c].to_numpy(dtype=float) for c in stream_cols]
    packed_cols = [np.nan_to_num(c, nan=0.0) for c in packed_cols]
    years = ordered["year"].to_numpy(dtype=float)

    windows: list[dict[str, Any]] = []
    means_series: list[dict[str, float]] = []
    for b in range(n_batches):
        lo = b * batch_size
        hi = min(n_events, lo + batch_size)
        if hi <= lo:
            break
        means = {
            c: round(float(packed_cols[i][lo:hi].mean()), 4)
            for i, c in enumerate(stream_cols)
        }
        years_lo, years_hi = float(years[lo]), float(years[hi - 1])
        year_from = int(np.floor(years_lo / 10) * 10)
        year_to = int(np.floor(years_hi / 10) * 10)
        windows.append(
            {
                "batch": b,
                "year_from": year_from,
                "year_to": year_to,
                "n": int(hi - lo),
                "means": means,
                "window_type": "tumbling",
            }
        )
        means_series.append(means)

    # ---- sliding window (rolling mean over the last `window` batches) ---- #
    frame = pd.DataFrame(means_series)
    rolling = frame.rolling(window=window, min_periods=1).mean()
    ewma = frame.ewm(span=window, adjust=False).mean()

    sliding: list[dict[str, Any]] = []
    for b, row in rolling.iterrows():
        entry: dict[str, Any] = {
            "batch": int(b),
            "year_from": windows[b]["year_from"],
            "year_to": windows[b]["year_to"],
            "label": f"{windows[b]['year_from']}s",
        }
        for c in stream_cols:
            entry[c] = round(float(row[c]), 4)
            entry[f"ewma_{c}"] = round(float(ewma.loc[b, c]), 4)
        sliding.append(entry)

    # ---- concept drift detection ----------------------------------------- #
    # Two things make this meaningful on a trending series:
    #   1. the test runs on the *smoothed* sliding series, since single batches of
    #      a shuffled corpus swing wildly by chance; and
    #   2. it compares the window's **step** (first difference) against the recent
    #      steps, not its level. A steadily rising feature is a trend, not a change
    #      point - drift is where the rate of change jumps (CUSUM/ADWIN idea).
    drift_points: list[dict[str, Any]] = []
    delta_frame = rolling.diff()
    history_span = max(window + 5, 8)
    for b in range(history_span + 1, len(means_series)):
        history = delta_frame.iloc[b - history_span : b]
        for c in stream_cols:
            hist = history[c].to_numpy(dtype=float)
            hist = hist[np.isfinite(hist)]
            current = float(delta_frame.iloc[b][c])
            if len(hist) < 3 or not np.isfinite(current):
                continue
            base = float(hist.mean())
            sd = float(hist.std(ddof=0))
            if sd <= 1e-9:
                continue
            z = (current - base) / sd
            if abs(z) > drift_z:
                drift_points.append(
                    {
                        "batch": b,
                        "year_from": windows[b]["year_from"],
                        "year_to": windows[b]["year_to"],
                        "feature": c,
                        "from_value": round(float(rolling.iloc[b - 1][c]), 4),
                        "to_value": round(float(rolling.iloc[b][c]), 4),
                        "delta": round(current, 4),
                        "baseline_step": round(base, 4),
                        "z_score": round(z, 3),
                    }
                )
    drift_points.sort(key=lambda d: -abs(d["z_score"]))

    payload_windows = windows[:max_windows]
    payload_sliding = sliding[:max_windows]
    elapsed = time.perf_counter() - t0

    return {
        "experiment": EXPERIMENT,
        "title": TITLE,
        "seconds": round(elapsed, 3),
        "features": stream_cols,
        "windows": payload_windows,
        "sliding": payload_sliding,
        "drift_points": drift_points[:20],
        "stats": {
            "events": int(n_events),
            "batches": n_batches,
            "batches_shown": len(payload_windows),
            "batch_size": batch_size,
            "window": window,
            "drift_z_threshold": drift_z,
            "late_events": late_count,
            "late_pct": round(100.0 * late_count / max(1, n_events), 3),
            "max_lateness_years": round(float(lateness_years.max()), 1),
            "avg_lateness_years": round(float(lateness_years[late_mask].mean()), 2)
            if late_count
            else 0.0,
            "drift_count": len(drift_points),
            "throughput_events_per_sec": int(n_events / elapsed) if elapsed > 0 else n_events,
            "watermark_lag_years": 0,
            "note": (
                "Arrival order is simulated as the CSV row order, which is not "
                "release-date sorted, so most events land behind the running "
                "watermark - the trade-off the lab asks about is that a larger "
                "watermark lag keeps more state but tolerates more late data. "
                "Drift is detected on the smoothed sliding series' first "
                "difference, so a slow trend is not misreported as N change points."
            ),
        },
        "concepts": [
            "event time vs arrival time",
            "watermark / late-arriving event accounting",
            "tumbling windows (fixed micro-batches)",
            "sliding windows + exponentially weighted moving average",
            "concept drift / change-point detection via z-score",
            "stream throughput measurement",
        ],
    }
