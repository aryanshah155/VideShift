"""Graph mining / social-network-analysis style analysis (Exp.7, CO5-LO5).

The lab performs SNA in R/igraph over a social graph: load data -> create network
-> degree histogram -> network diagram -> relationships + community detection.
The Spotify corpus has no explicit social edges, so the network is built from
**acoustic similarity**: a k-nearest-neighbour cosine graph over standardized
feature vectors. Every step of the manual's R script then has an analogue:

    get data / create network  -> k-NN cosine graph over sampled tracks
    histogram of node degree   -> degree distribution
    network diagram + layouts  -> Fruchterman-Reingold + degree-ring layouts
    highlighting degrees       -> node size/colour by degree centrality
    community detection        -> label propagation (+ modularity score)

Extra graph metrics that make the analysis defensible: connected components,
average clustering coefficient, graph density and PageRank influence.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd

EXPERIMENT = "Exp.7 / CO5-LO5"
TITLE = "Social network analysis: similarity graph, degrees, layouts, communities"


def _label_for(cluster_id: int) -> str:
    try:
        from ..pipeline.pandas_engine import _label_for as fn

        return fn(int(cluster_id))
    except Exception:
        return f"Profile {int(cluster_id)}"


def _components(n: int, adj: list[set[int]]) -> list[list[int]]:
    seen = [False] * n
    comps: list[list[int]] = []
    for start in range(n):
        if seen[start]:
            continue
        stack = [start]
        seen[start] = True
        comp: list[int] = []
        while stack:
            v = stack.pop()
            comp.append(v)
            for u in adj[v]:
                if not seen[u]:
                    seen[u] = True
                    stack.append(u)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    return comps


def _label_propagation(
    n: int, adj: list[set[int]], seed: int = 42, iterations: int = 20
) -> np.ndarray:
    """Deterministic label propagation community detection."""
    labels = np.arange(n)
    rng = np.random.default_rng(seed)
    for _ in range(iterations):
        changed = 0
        for v in rng.permutation(n):
            neighbours = adj[v]
            if not neighbours:
                continue
            counts: dict[int, int] = {}
            for u in neighbours:
                counts[labels[u]] = counts.get(labels[u], 0) + 1
            # most frequent neighbour label, ties broken by the smaller label id
            best = max(counts.items(), key=lambda kv: (kv[1], -kv[0]))[0]
            if labels[v] != best:
                labels[v] = best
                changed += 1
        if changed == 0:
            break
    # compact labels ordered by community size (0 = largest)
    order = pd.Series(labels).value_counts().index.tolist()
    remap = {old: new for new, old in enumerate(order)}
    return np.array([remap[label] for label in labels])


def _modularity(n: int, adj: list[set[int]], labels: np.ndarray) -> float:
    m = sum(len(a) for a in adj) / 2.0
    if m <= 0:
        return 0.0
    degrees = np.array([len(a) for a in adj], dtype=float)
    q = 0.0
    for c in np.unique(labels):
        members = np.where(labels == c)[0]
        l_c = 0.0
        for v in members:
            l_c += sum(1 for u in adj[int(v)] if labels[u] == c)
        l_c /= 2.0
        d_c = degrees[members].sum()
        q += l_c / m - (d_c / (2.0 * m)) ** 2
    return float(q)


def _pagerank(n: int, adj: list[set[int]], damping: float = 0.85, iterations: int = 40) -> np.ndarray:
    if n == 0:
        return np.zeros(0)
    rank = np.full(n, 1.0 / n)
    degrees = np.array([len(a) for a in adj], dtype=float)
    dangling = degrees == 0
    for _ in range(iterations):
        nxt = np.full(n, (1.0 - damping) / n)
        # contributions from non-dangling nodes
        for v in range(n):
            if dangling[v]:
                continue
            share = damping * rank[v] / degrees[v]
            for u in adj[v]:
                nxt[u] += share
        # dangling mass is redistributed uniformly
        if dangling.any():
            nxt += damping * rank[dangling].sum() / n
        if np.allclose(nxt, rank):
            rank = nxt
            break
        rank = nxt
    return rank


def _force_layout(
    n: int,
    edge_i: np.ndarray,
    edge_j: np.ndarray,
    *,
    iterations: int = 90,
    seed: int = 42,
) -> np.ndarray:
    """Fruchterman-Reingold force-directed layout (vectorised)."""
    rng = np.random.default_rng(seed)
    pos = rng.uniform(0.0, 100.0, (n, 2))
    area = 100.0 * 100.0
    k = np.sqrt(area / max(1, n))
    temperature = 12.0
    cooling = temperature / (iterations + 1)

    for _ in range(iterations):
        delta = pos[:, None, :] - pos[None, :, :]  # (n, n, 2)
        dist = np.sqrt((delta ** 2).sum(axis=-1))
        np.fill_diagonal(dist, np.inf)  # no self-interaction
        # Coincident nodes (possible after clipping) would give 0/0 -> NaN.
        dist = np.where(dist < 1e-9, 1e-9, dist)
        repulsion = (delta / (dist[:, :, None] ** 2)) * (k * k)
        disp = repulsion.sum(axis=1)

        if len(edge_i):
            d = pos[edge_i] - pos[edge_j]
            dl = np.linalg.norm(d, axis=1, keepdims=True)
            dl[dl == 0.0] = 1e-9
            attraction = (d / dl) * (dl ** 2 / k)
            np.add.at(disp, edge_i, -attraction)
            np.add.at(disp, edge_j, attraction)

        mag = np.linalg.norm(disp, axis=1, keepdims=True)
        mag = np.where(mag < 1e-12, 1e-12, mag)
        pos = pos + (disp / mag) * np.minimum(mag, temperature)
        temperature -= cooling

    pos = np.nan_to_num(pos, nan=0.0, posinf=0.0, neginf=0.0)
    lo, hi = pos.min(axis=0), pos.max(axis=0)
    span = np.where((hi - lo) <= 1e-12, 1.0, hi - lo)
    return (pos - lo) / span * 100.0


def _degree_layout(degrees: np.ndarray) -> np.ndarray:
    """Concentric rings: hubs near the centre, peripheral nodes on the outer ring."""
    n = len(degrees)
    if n == 0:
        return np.zeros((0, 2))
    if degrees.max() == degrees.min():
        ranks = np.zeros(n)
    else:
        ranks = (degrees - degrees.min()) / (degrees.max() - degrees.min())
    ring = np.where(ranks >= 0.66, 0, np.where(ranks >= 0.33, 1, 2))  # 0 = innermost
    radius = np.array([18.0, 34.0, 48.0])[ring]
    pos = np.zeros((n, 2))
    for r in range(3):
        members = np.where(ring == r)[0]
        if len(members) == 0:
            continue
        angles = np.linspace(0, 2 * np.pi, len(members), endpoint=False)
        pos[members, 0] = 50.0 + radius[members] * np.cos(angles)
        pos[members, 1] = 50.0 + radius[members] * np.sin(angles)
    return pos


def run_sna(
    df: pd.DataFrame,
    feature_cols: list[str],
    *,
    sample_n: int = 200,
    k_neighbors: int = 4,
    seed: int = 42,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    cols = [c for c in feature_cols if c in df.columns]
    if not cols or len(df) < 6:
        return {"experiment": EXPERIMENT, "error": "not enough data to build a graph"}

    n = min(sample_n, len(df))
    rng = np.random.default_rng(seed)
    idx = (
        rng.choice(len(df), size=n, replace=False)
        if len(df) > n
        else np.arange(len(df))
    )
    sub = df.iloc[np.sort(idx)].reset_index(drop=True)

    X = np.nan_to_num(sub[cols].to_numpy(dtype=float))
    mu, sd = X.mean(axis=0), X.std(axis=0, ddof=0)
    sd[sd == 0.0] = 1.0
    Z = (X - mu) / sd
    norms = np.linalg.norm(Z, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    Zn = Z / norms
    sim = Zn @ Zn.T
    np.fill_diagonal(sim, -2.0)

    kk = int(max(1, min(k_neighbors, n - 1)))
    neighbours = np.argsort(-sim, axis=1)[:, :kk]

    edge_weight: dict[tuple[int, int], float] = {}
    for i in range(n):
        for j in neighbours[i]:
            a, b = (i, int(j)) if i < j else (int(j), i)
            w = float(sim[a, b])
            if w > edge_weight.get((a, b), -2.0):
                edge_weight[(a, b)] = w

    edge_list = sorted(edge_weight.items(), key=lambda kv: -kv[1])
    edge_i = np.array([e[0][0] for e in edge_list], dtype=int) if edge_list else np.array([], dtype=int)
    edge_j = np.array([e[0][1] for e in edge_list], dtype=int) if edge_list else np.array([], dtype=int)

    adj: list[set[int]] = [set() for _ in range(n)]
    for a, b in edge_weight:
        adj[a].add(b)
        adj[b].add(a)
    degrees = np.array([len(a) for a in adj], dtype=float)

    # ---- community detection ------------------------------------------- #
    communities = _label_propagation(n, adj, seed=seed)
    modularity = _modularity(n, adj, communities)
    comps = _components(n, adj)
    pagerank = _pagerank(n, adj)

    # ---- clustering coefficient ---------------------------------------- #
    coeffs = np.zeros(n)
    for v in range(n):
        nb = list(adj[v])
        d = len(nb)
        if d < 2:
            continue
        links = sum(1 for a in range(d) for b in range(a + 1, d) if nb[b] in adj[nb[a]])
        coeffs[v] = 2.0 * links / (d * (d - 1))

    # ---- layouts -------------------------------------------------------- #
    force = _force_layout(n, edge_i, edge_j, seed=seed)
    ring = _degree_layout(degrees)

    # ---- degree histogram ----------------------------------------------- #
    max_deg = int(degrees.max()) if n else 0
    bins = list(range(0, max_deg + 2, 2)) or [0, 1]
    hist, edges = np.histogram(degrees, bins=bins)
    degree_histogram = [
        {"bin": f"{int(edges[i])}-{int(edges[i + 1]) - 1}", "count": int(hist[i])}
        for i in range(len(hist))
    ]

    # ---- community summaries -------------------------------------------- #
    cluster_series = (
        sub["cluster"].to_numpy() if "cluster" in sub.columns else np.zeros(n, dtype=int)
    )
    community_rows = []
    for c in np.unique(communities):
        members = np.where(communities == c)[0]
        member_clusters = cluster_series[members]
        dominant = int(pd.Series(member_clusters).mode().iloc[0]) if len(members) else -1
        share = (
            float((member_clusters == dominant).mean() * 100.0) if len(members) else 0.0
        )
        community_rows.append(
            {
                "community": int(c),
                "size": int(len(members)),
                "share_pct": round(100.0 * len(members) / n, 2),
                "avg_degree": round(float(degrees[members].mean()), 2),
                "dominant_cluster": dominant,
                "dominant_cluster_label": _label_for(dominant),
                "dominant_share_pct": round(share, 2),
            }
        )
    community_rows.sort(key=lambda r: -r["size"])

    # ---- nodes + edges --------------------------------------------------- #
    nodes = []
    for i in range(n):
        row = sub.iloc[i]
        nodes.append(
            {
                "id": str(row.get("id", i)),
                "name": str(row.get("name", ""))[:42],
                "artists": str(row.get("artists", ""))[:30],
                "cluster": int(cluster_series[i]),
                "community": int(communities[i]),
                "degree": int(degrees[i]),
                "clustering_coeff": round(float(coeffs[i]), 3),
                "pagerank": round(float(pagerank[i]), 5),
                "x": round(float(force[i, 0]), 2),
                "y": round(float(force[i, 1]), 2),
                "rx": round(float(ring[i, 0]), 2),
                "ry": round(float(ring[i, 1]), 2),
            }
        )
    edges = [
        {
            "source": int(a),
            "target": int(b),
            "weight": round(float(w), 4),
        }
        for (a, b), w in edge_list
    ]

    hubs = sorted(nodes, key=lambda nd: -nd["degree"])[:10]
    influential = sorted(nodes, key=lambda nd: -nd["pagerank"])[:10]

    return {
        "experiment": EXPERIMENT,
        "title": TITLE,
        "seconds": round(time.perf_counter() - t0, 3),
        "stats": {
            "nodes": n,
            "edges": len(edges),
            "density": round(2.0 * len(edges) / max(1, n * (n - 1)), 4),
            "avg_degree": round(float(degrees.mean()), 2),
            "max_degree": max_deg,
            "communities": int(len(community_rows)),
            "modularity": round(modularity, 4),
            "components": len(comps),
            "largest_component": len(comps[0]) if comps else 0,
            "avg_clustering_coefficient": round(float(coeffs.mean()), 4),
            "k_neighbors": kk,
            "sampled_from": int(len(df)),
            "isolated_nodes": int((degrees == 0).sum()),
        },
        "degree_histogram": degree_histogram,
        "communities": community_rows,
        "hubs": hubs,
        "influential": influential,
        "nodes": nodes,
        "edges": edges,
        "layouts": ["force", "degree_ring"],
        "concepts": [
            "network construction from a similarity matrix",
            "degree centrality + degree distribution histogram",
            "force-directed (Fruchterman-Reingold) layout",
            "degree-based concentric layout",
            "label propagation community detection",
            "modularity, density, clustering coefficient, components",
            "PageRank influence ranking",
        ],
    }
