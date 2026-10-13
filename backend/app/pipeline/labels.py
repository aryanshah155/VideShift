"""Interpret a fitted cluster from its own profile.

A KMeans cluster id is just an arbitrary integer assigned by the initialisation
order, so naming a cluster from a fixed ``{0: "Acoustic", 1: "Electronic"}``
table prints labels that can flatly contradict the cluster they describe (and
swap meaning whenever the centroids come out in a different order).

Instead, every cluster is named from the mean feature values it actually has,
using the documented rule cascade below. The rules are deliberately simple and
readable so the label can be defended in the report alongside the cluster
profile table.
"""

from __future__ import annotations

from typing import Any, Iterable

# Thresholds operate on the raw (unscaled) feature means, because those are the
# numbers the UI shows in the cluster-profile table.
RULES: list[tuple[str, str]] = [
    ("instrumentalness >= 0.50", "Instrumental / Ambient"),
    ("speechiness >= 0.15", "Spoken / Lyrical"),
    ("acousticness >= 0.55 and energy <= 0.50", "Acoustic / Organic"),
    ("energy >= 0.75 and acousticness <= 0.20", "High-Energy Electronic"),
    ("danceability >= 0.60 and valence >= 0.60", "Bright / Upbeat"),
    ("danceability >= 0.60", "Rhythmic / Dance"),
    ("energy >= 0.68 and acousticness <= 0.30", "High-Energy Electronic"),
    ("energy >= 0.70 and loudness >= -6.0", "Loud / Intense"),
    ("energy <= 0.40 and valence <= 0.45", "Mellow / Low-Energy"),
]


def name_cluster(means: dict[str, float]) -> str:
    """Return the descriptive label for one cluster's mean feature profile."""
    m = means or {}
    inst = float(m.get("instrumentalness", 0.0) or 0.0)
    ac = float(m.get("acousticness", 0.0) or 0.0)
    en = float(m.get("energy", 0.0) or 0.0)
    da = float(m.get("danceability", 0.0) or 0.0)
    va = float(m.get("valence", 0.0) or 0.0)
    sp = float(m.get("speechiness", 0.0) or 0.0)
    lo = float(m.get("loudness", -10.0) or -10.0)

    if inst >= 0.50:
        return "Instrumental / Ambient"
    if sp >= 0.15:
        return "Spoken / Lyrical"
    if ac >= 0.55 and en <= 0.50:
        return "Acoustic / Organic"
    if en >= 0.75 and ac <= 0.20:
        return "High-Energy Electronic"
    if da >= 0.60 and va >= 0.60:
        return "Bright / Upbeat"
    if da >= 0.60:
        return "Rhythmic / Dance"
    if en >= 0.68 and ac <= 0.30:
        return "High-Energy Electronic"
    if en >= 0.70 and lo >= -6.0:
        return "Loud / Intense"
    if en <= 0.40 and va <= 0.45:
        return "Mellow / Low-Energy"
    return "Vocal / Pop"


def label_clusters(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Set ``label`` on every cluster profile from its own ``means``.

    Two clusters that land on the same rule are disambiguated by appending the
    cluster id, so the UI never shows the same name twice for different rows.
    """
    seen: dict[str, int] = {}
    for profile in sorted(profiles, key=lambda p: int(p.get("cluster", 0))):
        base = name_cluster(profile.get("means") or {})
        count = seen.get(base, 0)
        seen[base] = count + 1
        cid = int(profile.get("cluster", 0))
        profile["label"] = base if count == 0 else f"{base} (C{cid})"
    return profiles


def label_map(profiles: Iterable[dict[str, Any]] | None) -> dict[int, str]:
    """``{cluster_id: label}`` lookup for analyses that only know the id."""
    lookup: dict[int, str] = {}
    for profile in profiles or []:
        try:
            lookup[int(profile["cluster"])] = str(
                profile.get("label") or name_cluster(profile.get("means") or {})
            )
        except (KeyError, TypeError, ValueError):
            continue
    return lookup
