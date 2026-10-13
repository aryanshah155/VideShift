"""Render the diagrams used in the VibeShift mini-project report.

Every figure is generated from the project's own code/data so the report can be
regenerated after any change:

    cd backend && .venv/Scripts/python ../report/make_diagrams.py

Outputs land in report/assets/.
"""

from __future__ import annotations

import io
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
DATA = os.path.join(HERE, "data")
os.makedirs(ASSETS, exist_ok=True)

INK = "#1f2933"
ACCENT = "#1db954"       # VibeShift green
BLUE = "#3b5bdb"
AMBER = "#e8a33d"
GREY = "#e4e7eb"
RED = "#e03131"


def _load(name):
    with io.open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def box(ax, x, y, w, h, text, fc="white", ec=INK, fs=9, tc=INK, bold=False, radius=0.02):
    ax.add_patch(
        mpatches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle=f"round,pad=0.004,rounding_size={radius}",
            linewidth=1.3, edgecolor=ec, facecolor=fc, zorder=2,
        )
    )
    ax.text(
        x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
        color=tc, zorder=3, wrap=True,
        fontweight="bold" if bold else "normal",
    )


def arrow(ax, xy_from, xy_to, color=INK, style="-|>", lw=1.3, ls="-"):
    ax.annotate(
        "", xy=xy_to, xytext=xy_from,
        arrowprops=dict(arrowstyle=style, color=color, lw=lw, linestyle=ls,
                        shrinkA=1, shrinkB=1),
        zorder=4,
    )


def blank(w, h):
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def save(fig, name):
    path = os.path.join(ASSETS, name)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", path)


# --------------------------------------------------------------------------
# Figure: overall system architecture
# --------------------------------------------------------------------------
def architecture():
    fig, ax = blank(11, 7.2)

    ax.text(0.5, 0.975, "VibeShift — 3-tier architecture", ha="center", va="top",
            fontsize=13, fontweight="bold", color=INK)

    # presentation tier
    box(ax, 0.04, 0.79, 0.92, 0.13, "", fc="#f4fbf6", ec=ACCENT)
    ax.text(0.06, 0.905, "PRESENTATION TIER — React 18 SPA (Vite, Tailwind, Recharts)",
            fontsize=9.5, fontweight="bold", color="#0f7a3d", va="top")
    for i, (t, s) in enumerate([
        ("Dashboard", "run config + year\nwindow + live console"),
        ("Results", "heatmaps, PCA,\nbenchmark, BDA suite"),
        ("Concepts", "33 BDA concepts\nwith live evidence"),
        ("Track Explorer", "filters + Bloom\nmembership verdict"),
    ]):
        x = 0.055 + i * 0.229
        box(ax, x, 0.795, 0.215, 0.072, f"{t}\n{s}", fc="white", ec=ACCENT, fs=7.6)

    # api tier
    box(ax, 0.04, 0.40, 0.92, 0.34, "", fc="#f6f7ff", ec=BLUE)
    ax.text(0.06, 0.715, "APPLICATION TIER — FastAPI / uvicorn (REST + background job runner)",
            fontsize=9.5, fontweight="bold", color="#2b3ea8", va="top")

    for i, t in enumerate([
        "/api/dataset/status\n/api/engine\n/api/runs (POST/GET)\n/api/runs/{id}/results",
        "/api/runs/{id}/tracks\nBloom lookup route",
        "/api/concepts\n(concept → evidence)",
        "/api/runs/{id}/notebook\n(.ipynb export)",
    ]):
        x = 0.055 + i * 0.229
        box(ax, x, 0.575, 0.215, 0.115, t, fc="white", ec=BLUE, fs=7.4)

    box(ax, 0.055, 0.425, 0.42, 0.115,
        "PipelineRunner (worker thread) + ThreadPoolExecutor\n"
        "15 stage callbacks → run status, log, per-stage timings",
        fc="white", ec=BLUE, fs=7.9)
    box(ax, 0.525, 0.425, 0.42, 0.115,
        "Engines: PySpark MLlib (primary) / pandas + scikit-learn (fallback)\n"
        "BDA suite: HDFS · MapReduce · Bloom · graph · streaming · ML · NoSQL · EDA",
        fc="white", ec=BLUE, fs=7.9)

    # data tier
    box(ax, 0.04, 0.06, 0.92, 0.27, "", fc="#fffaf0", ec=AMBER)
    ax.text(0.06, 0.305, "DATA TIER", fontsize=9.5, fontweight="bold",
            color="#9a6b00", va="top")
    box(ax, 0.055, 0.10, 0.28, 0.155,
        "tracks_features.csv\n329.7 MB · 1,204,025 rows · 24 cols\n"
        "Spotify audio-feature corpus",
        fc="white", ec=AMBER, fs=7.8)
    box(ax, 0.355, 0.10, 0.28, 0.155,
        "MongoDB  vibeshift.runs\nschemaless run documents\n(stages, config, log, results)",
        fc="white", ec=AMBER, fs=7.8)
    box(ax, 0.655, 0.10, 0.285, 0.155,
        "Per-run Parquet store\ndata/_runs/<run-id>/tracks.parquet\n(track → cluster assignments)",
        fc="white", ec=AMBER, fs=7.8)

    arrow(ax, (0.5, 0.79), (0.5, 0.745), color=ACCENT)
    arrow(ax, (0.4, 0.74), (0.4, 0.775), color=ACCENT, style="-|>")
    arrow(ax, (0.5, 0.40), (0.5, 0.335), color=AMBER)
    arrow(ax, (0.3, 0.33), (0.3, 0.365), color=AMBER, style="-|>")
    save(fig, "fig_architecture.png")


# --------------------------------------------------------------------------
# Figure: end-to-end pipeline
# --------------------------------------------------------------------------
def pipeline():
    results = _load("results.json")
    timings = results["timings"]
    bda = results["bda"]

    fig, ax = blank(11, 5.6)
    ax.text(0.5, 0.97, "Execution pipeline of a single run (861,542 rows clean)",
            ha="center", va="top", fontsize=12.5, fontweight="bold", color=INK)

    core = [
        ("1 ingest", "CSV → DataFrame\n4.41 s", ACCENT),
        ("2 clean", f"cast strikes out\nrows → {results['rows_clean']:,}", BLUE),
        ("3 assemble", f"vector + scale\ntimings['assemble']", BLUE),
        ("4 k-means", f"k={results['config_used']['k']} · {timings['kmeans']:.2f} s\n"
                      f"silhouette {results['silhouette']:.3f}", BLUE),
        ("5 PCA", f"2-D projection\n{timings['pca']:.2f} s", BLUE),
        ("6 aggregate", f"decade × cluster\n{timings['aggregate']:.2f} s", BLUE),
        ("7 benchmark", f"vectorised vs loop\n×{results['benchmark']['speedup']:.1f}", AMBER),
    ]
    w = 0.122
    for i, (name, sub, col) in enumerate(core):
        x = 0.035 + i * 0.1355
        box(ax, x, 0.60, w, 0.22, "", fc="white", ec=col)
        ax.text(x + w / 2, 0.785, name, ha="center", va="center", fontsize=9,
                fontweight="bold", color=col)
        ax.text(x + w / 2, 0.695, sub.replace("timings['assemble']", f"{timings['assemble']:.2f} s"),
                ha="center", va="center", fontsize=7.3, color=INK)
        if i:
            arrow(ax, (x - 0.014, 0.715), (x - 0.004, 0.715))

    ax.text(0.035, 0.545, "Big Data Analytics suite — every stage writes its evidence into the run document:",
            fontsize=9.2, fontweight="bold", color=INK, va="top")

    names = ["HDFS\nExp.1", "MapReduce\nExp.4/5", "Bloom filter\nExp.6",
             "Graph\nExp.7", "Streaming\nCO4", "MLlib-style ML\nExp.2",
             "MongoDB\nExp.3", "EDA + viz\nExp.8"]
    for i, n in enumerate(names):
        x = 0.035 + i * 0.1185
        colour = ACCENT if i in (1, 6, 7) else GREY
        box(ax, x, 0.33, 0.107, 0.16, n, fc="white", ec=colour, fs=7.6, bold=True)
        arrow(ax, (0.5, 0.60), (x + 0.053, 0.50), color="#adb5bd", lw=0.7, style="-|>")

    box(ax, 0.035, 0.06, 0.93, 0.19,
        "Run document (MongoDB  vibeshift.runs)  →  Dashboard console · Results page · "
        "Concepts page (live evidence per concept) · track explorer · section-wise .ipynb export",
        fc="#f4fbf6", ec=ACCENT, fs=8.4)
    for i in range(len(names)):
        pass
    arrow(ax, (0.5, 0.33), (0.5, 0.25), color=ACCENT)
    save(fig, "fig_pipeline.png")


# --------------------------------------------------------------------------
# Figure: MapReduce execution model with real counters
# --------------------------------------------------------------------------
def mapreduce():
    results = _load("results.json")
    job = results["bda"]["mapreduce"]["jobs"][0]
    st = job["stats"]

    fig, ax = blank(11, 4.9)
    ax.text(0.5, 0.965, "MapReduce execution model — word count over 25,000 track titles",
            ha="center", va="top", fontsize=12.5, fontweight="bold", color=INK)

    stages = [
        ("Input split", f"{st['input_records']:,}\nrecords", 0),
        ("MAP", f"emit (word, 1)\n{st['map_output_pairs']:,} pairs", 1),
        ("COMBINE", f"{st['combine_output_pairs']:,} pairs\n−{st['combine_saved_pct']:.0f}% shuffle",
         2),
        ("SHUFFLE", f"hash partition\n{st['shuffle_groups']:,} groups", 3),
        ("REDUCE", f"sum per word\n{st['output_records']:,} keys", 4),
        ("Output", f"top keys: {job['output'][0]['key']}\n{job['output'][0]['value']}×", 5),
    ]
    w, h = 0.135, 0.235
    for name, sub, i in stages:
        x = 0.025 + i * 0.163
        col = ACCENT if name in ("MAP", "COMBINE", "SHUFFLE", "REDUCE") else INK
        box(ax, x, 0.60, w, h, "", fc="white", ec=col)
        ax.text(x + w / 2, 0.77, name, ha="center", fontsize=9, fontweight="bold", color=col)
        ax.text(x + w / 2, 0.665, sub, ha="center", va="center", fontsize=7.4)
        if i:
            arrow(ax, (x - 0.020, 0.715), (x - 0.006, 0.715))

    t = st["timings"]
    phases = ["map", "shuffle", "combine", "reduce"]
    vals = [t[p] for p in phases]

    ax.text(0.03, 0.545, "Phase timings (seconds)", fontsize=9.3,
            fontweight="bold", va="top")
    bax = ax.inset_axes([0.03, 0.06, 0.42, 0.42])
    bax.bar([0, 1, 2, 3], vals, color=[ACCENT, BLUE, AMBER, RED], zorder=3, width=0.62)
    for i, v in enumerate(vals):
        bax.text(i, v + max(vals) * 0.05, f"{v * 1000:.1f} ms", ha="center",
                 fontsize=7.6, zorder=4)
    bax.set_xlim(-0.6, 3.6)
    bax.set_ylim(0, max(vals) * 1.42)
    bax.set_yticks([])
    bax.set_xticks([0, 1, 2, 3], phases)
    bax.tick_params(labelsize=8)
    for side in ("top", "right"):
        bax.spines[side].set_visible(False)

    box(ax, 0.52, 0.06, 0.44, 0.42,
        "Combiner saves 70% of the shuffle volume;\n"
        f"{st['reducers']} reducers, each owning one crc32(word) mod 4 partition.\n"
        "All four phases are timed and exported as evidence.",
        fc="#f4fbf6", ec=ACCENT, fs=7.8)
    ax.text(0.03, 0.505, f"Job wall time: {st['timings']['total'] * 1000:.0f} ms",
            fontsize=9.5, fontweight="bold", color="#0f7a3d", va="top")
    save(fig, "fig_mapreduce.png")


# --------------------------------------------------------------------------
# Figure: use-case diagram
# --------------------------------------------------------------------------
def usecase():
    fig, ax = blank(10.5, 6.4)
    ax.text(0.5, 0.975, "Use-case diagram — VibeShift", ha="center", va="top",
            fontsize=12.5, fontweight="bold")

    ax.add_patch(mpatches.Ellipse((0.16, 0.5), 0.06, 0.34, fill=False, ec=INK, lw=1.2))
    ax.text(0.16, 0.5, "Student /\nResearcher", ha="center", va="center", fontsize=9,
            fontweight="bold", rotation=0)

    ax.add_patch(mpatches.Ellipse((0.62, 0.5), 0.30, 0.74, fill=False, ec=BLUE, lw=1.2))
    ax.text(0.62, 0.90, "VibeShift system", ha="center", fontsize=9.5,
            fontweight="bold", color="#2b3ea8")

    cases = [
        ("Check dataset & engine status", 0.82),
        ("Configure a run (k, year window, features)", 0.72),
        ("Launch run and watch live stages", 0.62),
        ("Inspect vibe-shift heatmap & PCA", 0.52),
        ("Inspect MapReduce job statistics", 0.42),
        ("Query Mongo run documents", 0.32),
        ("Explore tracks / Bloom lookup", 0.22),
        ("Read concept → evidence catalogue", 0.12),
        ("Export section-wise Colab notebook", 0.02),
    ]
    for name, y in cases:
        ax.add_patch(mpatches.Ellipse((0.60, y + 0.045), 0.52, 0.075, fill=True,
                                      facecolor="#f4fbf6" if "MapReduce" in name or
                                      "Mongo" in name or "heatmap" in name else "white",
                                      edgecolor=ACCENT if "MapReduce" in name or
                                      "Mongo" in name or "heatmap" in name else BLUE,
                                      lw=1.1))
        ax.text(0.60, y + 0.045, name, ha="center", va="center", fontsize=8.2)
        arrow(ax, (0.20, 0.5), (0.33, y + 0.045), color="#adb5bd", lw=0.7)

    ax.text(0.02, 0.03,
            "Green use cases are the report's core scope (MapReduce, MongoDB, visualisation);\n"
            "the remaining use cases stay implemented and reachable but are secondary.",
            fontsize=7.8, color="#555")
    save(fig, "fig_usecase.png")


# --------------------------------------------------------------------------
# Figure: DFD level 0 and level 1
# --------------------------------------------------------------------------
def dfd():
    fig, ax = blank(10.5, 6.0)
    ax.text(0.5, 0.975, "Data-flow diagram — context (Level 0) and Level 1",
            ha="center", va="top", fontsize=12.5, fontweight="bold")

    # context diagram
    box(ax, 0.02, 0.52, 0.17, 0.20, "Researcher\n(actor)", fc="white", ec=INK, fs=8.6)
    ax.add_patch(mpatches.Circle((0.40, 0.62), 0.135, facecolor="#f4fbf6", edgecolor=ACCENT, lw=1.4))
    ax.text(0.40, 0.645, "0\nVibeShift", ha="center", fontsize=9.5, fontweight="bold")
    ax.text(0.40, 0.565, "analytics engine", ha="center", fontsize=7.4)
    box(ax, 0.68, 0.52, 0.30, 0.20, "Spotify corpus\nCSV 329.7 MB", fc="white", ec=AMBER, fs=8.6)
    arrow(ax, (0.195, 0.66), (0.265, 0.66))
    ax.text(0.23, 0.688, "run config,\nfilter window", ha="center", fontsize=7.2, color=INK)
    arrow(ax, (0.265, 0.56), (0.195, 0.56))
    ax.text(0.23, 0.505, "heatmaps,\nconcept evidence", ha="center", fontsize=7.2, color=INK)
    arrow(ax, (0.68, 0.66), (0.535, 0.66))
    ax.text(0.61, 0.688, "audio features", ha="center", fontsize=7.2, color=INK)

    ax.plot([0.02, 0.98], [0.44, 0.44], color="#ced4da", lw=1)

    # level 1
    ax.text(0.02, 0.41, "Level 1 — decomposition of process 0", fontsize=9.3,
            fontweight="bold", va="top")
    procs = [
        ("1.0\nIngest & clean", 0.03, ACCENT),
        ("2.0\nAssemble &\ncluster", 0.28, BLUE),
        ("3.0\nAggregate\n(vibe shifts)", 0.53, BLUE),
        ("4.0\nBDA analyses", 0.78, ACCENT),
    ]
    for name, x, col in procs:
        ax.add_patch(mpatches.Circle((x + 0.09, 0.24), 0.085, facecolor="white",
                                     edgecolor=col, lw=1.4))
        ax.text(x + 0.09, 0.24, name, ha="center", va="center", fontsize=7.6,
                fontweight="bold", color=col)
        if x > 0.03:
            arrow(ax, (x - 0.075, 0.24), (x + 0.001, 0.24))

    stores = [("D1  tracks_features.csv", 0.05), ("D2  run documents (MongoDB)", 0.42),
              ("D3  Parquet track store", 0.75)]
    for name, x in stores:
        ax.plot([x, x + 0.21], [0.055, 0.055], color=INK, lw=1.5)
        ax.plot([x, x + 0.21], [0.03, 0.03], color=INK, lw=1.5)
        ax.plot([x, x], [0.03, 0.055], color=INK, lw=1.5)
        ax.plot([x + 0.21, x + 0.21], [0.03, 0.055], color=INK, lw=1.5)
        ax.text(x + 0.105, 0.0425, name, ha="center", va="center", fontsize=7.2)
    arrow(ax, (0.12, 0.155), (0.12, 0.058), color="#adb5bd", lw=0.8, style="-")
    arrow(ax, (0.51, 0.155), (0.51, 0.058), color="#adb5bd", lw=0.8, style="-")
    arrow(ax, (0.855, 0.155), (0.855, 0.058), color="#adb5bd", lw=0.8, style="-")
    save(fig, "fig_dfd.png")


# --------------------------------------------------------------------------
# Figure: class diagram of the backend
# --------------------------------------------------------------------------
def classdiagram():
    fig, ax = blank(11, 6.6)
    ax.text(0.5, 0.975, "Class diagram — backend components", ha="center", va="top",
            fontsize=12.5, fontweight="bold")

    def cls(x, y, w, h, title, attrs, methods, col=BLUE):
        box(ax, x, y, w, h, "", fc="white", ec=col)
        ax.plot([x, x + w], [y + h - 0.055, y + h - 0.055], color=col, lw=1.0)
        ax.text(x + w / 2, y + h - 0.028, title, ha="center", va="center",
                fontsize=8.4, fontweight="bold", color=col)
        ty = y + h - 0.075
        for a in attrs:
            ax.text(x + 0.008, ty, a, ha="left", va="top", fontsize=6.9)
            ty -= 0.030
        ax.plot([x, x + w], [ty + 0.012, ty + 0.012], color=col, lw=0.7, ls=":")
        ty -= 0.005
        for m in methods:
            ax.text(x + 0.008, ty, m, ha="left", va="top", fontsize=6.9, color="#333")
            ty -= 0.030

    cls(0.02, 0.60, 0.29, 0.30, "RunStore",
        ["settings: Settings", "mongo: MongoClient | None"],
        ["save(run)  ·  get(run_id)", "list(limit)  ·  json fallback"],
        col=AMBER)
    cls(0.35, 0.60, 0.30, 0.30, "PipelineRunner",
        ["store, engine_factory", "executor: ThreadPoolExecutor"],
        ["submit(cfg) -> run_id", "_run()  ·  _stage(name, fn)", "progress -> run.log + stages"],
        col=BLUE)
    cls(0.69, 0.60, 0.29, 0.30, "SparkEngine / PandasEngine",
        ["feature_cols: list[str]", "k, seed=42"],
        ["run(df, cfg, progress) -> dict", "clean · assemble · kmeans · pca",
         "aggregate · benchmark"],
        col=ACCENT)

    cls(0.02, 0.24, 0.29, 0.28, "BdaSuite (app/bda)",
        ["modules: hdfs, mapreduce,", "bloom, graph, streaming,",
         "ml_models, nosql, eda"],
        ["run_all(df, cfg, sample) -> dict", "summary() -> coverage", "catalog.core_concepts()"],
        col=ACCENT)
    cls(0.35, 0.24, 0.30, 0.28, "Routers (FastAPI)",
        ["runs, dataset, concepts,", "notebook"],
        ["POST /api/runs", "GET  /api/runs/{id}/results", "GET  /api/runs/{id}/notebook"],
        col=BLUE)
    cls(0.69, 0.24, 0.29, 0.28, "TrackStore / notebook_export",
        ["parquet path per run", "bloom filter of title tokens"],
        ["page(filters) -> rows", "membership(term) -> verdict", "build_ipynb(results) -> bytes"],
        col=AMBER)

    arrow(ax, (0.35, 0.75), (0.31, 0.75), color=INK, lw=0.9)
    arrow(ax, (0.65, 0.75), (0.69, 0.75), color=INK, lw=0.9)
    arrow(ax, (0.50, 0.60), (0.50, 0.52), color=INK, lw=0.9)
    arrow(ax, (0.16, 0.60), (0.16, 0.52), color=INK, lw=0.9)
    arrow(ax, (0.83, 0.60), (0.83, 0.52), color=INK, lw=0.9)
    save(fig, "fig_class.png")


# --------------------------------------------------------------------------
# Figure: correlation heatmap straight from the EDA module output
# --------------------------------------------------------------------------
def correlation_heatmap():
    results = _load("results.json")
    eda = results["bda"]["eda"]
    corr = eda["correlation"]
    cols = eda["feature_columns"]
    m = np.array([[corr[a][b] for b in cols] for a in cols])

    fig, ax = plt.subplots(figsize=(7.6, 6.4), dpi=200)
    im = ax.imshow(m, cmap="RdYlGn", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols)), cols, rotation=45, ha="right", fontsize=8.5)
    ax.set_yticks(range(len(cols)), cols, fontsize=8.5)
    for i in range(len(cols)):
        for j in range(len(cols)):
            ax.text(j, i, f"{m[i, j]:.2f}", ha="center", va="center", fontsize=7,
                    color="black" if abs(m[i, j]) < 0.6 else "white")
    ax.set_title("Pearson correlation of the eight audio features (n = 861,542)",
                 fontsize=10.5, fontweight="bold", pad=12)
    fig.colorbar(im, ax=ax, shrink=0.8, label="r")
    save(fig, "fig_correlation.png")


# --------------------------------------------------------------------------
# Figure: cluster sizes and decade composition (from the same run)
# --------------------------------------------------------------------------
def cluster_profile():
    results = _load("results.json")
    clusters = results["clusters"]
    names = [c["label"] for c in clusters]
    sizes = [c["size"] for c in clusters]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), dpi=200)
    colours = ["#1db954", "#4f46e5", "#f59e0b", "#ef4444", "#06b6d4"]

    axes[0].barh(names[::-1], sizes[::-1], color=colours[: len(names)][::-1], zorder=3)
    for i, v in enumerate(sizes[::-1]):
        axes[0].text(v + 4000, i, f"{v:,}", va="center", fontsize=8)
    axes[0].set_title("Cluster sizes (k = 5)", fontsize=10.5, fontweight="bold")
    axes[0].set_xlim(0, max(sizes) * 1.25)
    axes[0].tick_params(labelsize=8)

    decades = [d["decade"] for d in results["decades"]]
    bottom = np.zeros(len(decades))
    for ci, c in enumerate(clusters):
        shares = [d["shares"].get(str(c["cluster"]), 0.0) for d in results["decades"]]
        axes[1].bar(decades, shares, bottom=bottom, color=colours[ci],
                    label=c["label"], zorder=3, edgecolor="white", linewidth=0.4)
        bottom += np.array(shares)
    axes[1].set_title("Decade composition — the vibe-shift heatmap as a stacked view",
                      fontsize=10.5, fontweight="bold")
    axes[1].set_ylabel("share of decade (%)", fontsize=9)
    axes[1].set_xlabel("decade", fontsize=9)
    axes[1].legend(fontsize=7, loc="lower left", framealpha=0.9)
    axes[1].tick_params(labelsize=8)
    fig.tight_layout()
    save(fig, "fig_clusters.png")


if __name__ == "__main__":
    architecture()
    pipeline()
    mapreduce()
    usecase()
    dfd()
    classdiagram()
    correlation_heatmap()
    cluster_profile()
    print("diagrams done")
