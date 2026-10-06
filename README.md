# VibeShift — Spotify "Vibe Shift" Acoustic Clustering

A full-stack analytics app that quantifies historical **vibe shifts** in popular music:
distributed K-Means clustering + PCA over Spotify audio features (danceability, energy,
valence, tempo, acousticness, …), aggregated by release decade into interactive heatmaps.

Built from a Big Data Analytics mini-project Colab notebook (PySpark MLlib pipeline over
the Spotify 1.2M+ Songs dataset), turned into a production-style app with a Python backend
and a React dashboard — following the planning methodology of
[gstack](https://github.com/garrytan/gstack) (see [docs/gstack-methodology.md](docs/gstack-methodology.md)).

## Features

- **Dashboard** — dataset status (rows, columns, tracks-per-decade histogram), engine badge
  (PySpark vs pandas fallback), run configuration (k, feature toggles, best-k silhouette sweep,
  row sampling), live stage console with per-stage timings, and run history. The **Year from /
  Year to** inputs take their `min`/`max` from the dataset's real year range, with quick buttons
  for the full range and the 99%-of-corpus range plus a live estimate of how many tracks the
  selected window covers.
- **Results** — the vibe-shift heatmap (decade × cluster shares), cluster-profile heatmap,
  PCA scatter (2D projection), decade trend lines, cluster sizes, silhouette sweep, and the
  execution benchmark card, followed by the **Big Data Analytics suite**.
- **Big Data Analytics suite** (core portion) — MapReduce job inspector, live MongoDB/NoSQL
  console, and the statistics/visualization panels. Five further analyses (HDFS, Bloom filter,
  network, streams, supervised ML) are implemented and executed on every run but tucked behind
  an “additional analyses” toggle.
- **Concepts page** — every technique mapped to the CSC702 lab manual experiment and course
  outcome, each with the live number it produced in the selected run and the JSON path holding
  its evidence.
- **Track explorer** — search + cluster/decade filters over every track's cluster assignment,
  with a live Bloom-filter membership verdict for the search term.
- **Notebook export** — one-click section-wise `.ipynb` reproducing the Colab pipeline with all
  the debugging fixes baked in, the BDA sections, and a markdown snapshot of the run's results.

## Architecture

```
vibeshift/
├── docker-compose.yml          # MongoDB
├── backend/
│   ├── requirements.txt
│   ├── data/                   # ← place tracks_features.csv here
│   └── app/
│       ├── main.py             # FastAPI app
│       ├── config.py           # env settings
│       ├── schema.py           # dataset column schema
│       ├── schemas.py          # API models
│       ├── notebook_export.py  # .ipynb generator (Colab pipeline + BDA sections)
│       ├── store.py            # Mongo store + JSON fallback + stale-doc detection
│       ├── routers/            # runs, dataset+concepts, notebook endpoints
│       ├── pipeline/
│       │   ├── ingest.py       # CSV/Parquet loading, dataset status + year range
│       │   ├── prepare.py      # cleaning, casting, decade, scaling
│       │   ├── pandas_engine.py# single-node engine (sklearn)
│       │   ├── spark_engine.py # PySpark MLlib engine
│       │   ├── engines.py      # engine detection/selection
│       │   ├── runner.py       # threaded job runner (clustering + BDA stages)
│       │   └── tracks.py       # per-run Parquet track store + Bloom lookup
│       ├── bda/                # Big Data Analytics suite (one module per technique)
│       │   ├── catalog.py      # concept registry + core-portion flags
│       │   ├── mapreduce.py    # Exp.4/5  map/shuffle/combine/reduce runtime
│       │   ├── nosql.py        # Exp.3    MongoDB console (read-only)
│       │   ├── eda.py          # Exp.8    statistics, correlation, outliers
│       │   ├── hdfs.py         # Exp.1    block/replica model + hdfs transcript
│       │   ├── bloom.py        # Exp.6    Bloom filter + lab tables
│       │   ├── graph.py        # Exp.7    similarity graph, communities, layouts
│       │   ├── ml_models.py    # Exp.2    supervised ML, elbow, dendrogram
│       │   └── streaming.py    # CO4      windows, watermark, drift detection
│       ├── scripts/            # prune_runs.py maintenance tool
│       └── tests/              # pytest suite
└── frontend/
    └── src/                    # Vite + React 18 + Tailwind + Recharts
```

**API**: `POST /api/runs` · `GET /api/runs` · `GET /api/runs/{id}` ·
`GET /api/runs/{id}/results` · `GET /api/runs/{id}/tracks?search&cluster&decade&page` ·
`GET /api/runs/{id}/bloom?term=` · `GET /api/runs/{id}/notebook` ·
`GET /api/dataset/status` · `GET /api/concepts` · `GET /api/engine` · `GET /api/store`

## Quick start

### 1. Dataset

Download [Spotify 1.2M+ Songs](https://www.kaggle.com/datasets/rodolfofigueroa/spotify-12m-songs)
from Kaggle (free account → download zip) and place `tracks_features.csv` in `backend/data/`.
The dashboard shows exactly where the file is expected.

### 2. MongoDB (optional but recommended)

```bash
docker compose up -d
```

If Mongo is unreachable, the app automatically falls back to a JSON-file store
(`backend/data/_store/runs.json`) — nothing else changes.

### 3. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
# .venv/bin/pip install -r requirements.txt     # macOS/Linux
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
```

### 5. Run the pipeline

Open http://localhost:5173, confirm the dataset card says **Ready**, configure k / year range,
and press **▶ Run pipeline**. The stage console shows ingest → clean → assemble → kmeans →
pca → aggregate → benchmark → hdfs → mapreduce → bloom → graph → streaming → ml → nosql → eda.

## Big Data Analytics mapping (CSC702 lab manual)

Every analysis runs inside the same pipeline, on the same cleaned and clustered records, and
reports its numbers into the run's `results.json` (`bda` block) and the UI.

**Core portion of the mini-project:**

| Experiment | Concept | Where it lives |
|---|---|---|
| Exp.3 | NoSQL with MongoDB — schemaless run documents, 26-command console, nested/array queries, `$group` pipeline | `bda/nosql.py`, `store.py` |
| Exp.4 | MapReduce word count over track titles | `bda/mapreduce.py` |
| Exp.5 | MapReduce aggregates (with combiner), map-side join, top-N sorting, inverted index search | `bda/mapreduce.py` |
| Exp.8 | Data visualization — decade × cluster heatmap, PCA scatter, trends, correlation heatmap, outliers | `frontend/src/pages/RunResults.jsx`, `bda/eda.py` |

**Additional analyses** (implemented and executed on every run, presented behind a toggle):
Exp.1 HDFS block/replica model and `hdfs dfs` transcript · Exp.2 supervised era classification
(RandomForest/DecisionTree/LogisticRegression on a 70/30 split), elbow + silhouette model
selection, Ward dendrogram · Exp.6 Bloom filter (optimal sizing, lab ASCII/bit tables,
search pre-filter) · Exp.7 similarity-network analysis with degree distribution, force and
degree-ring layouts, label-propagation communities and modularity · CO4 event-time windows,
watermark/late arrivals and change-point drift detection.

`GET /api/concepts` returns the whole registry annotated with `primary: true/false` so the
frontend can present the core three prominently without deleting anything.

## Engines: Spark vs pandas

The backend prefers **PySpark MLlib** (VectorAssembler → StandardScaler → KMeans → PCA) when
`pyspark` is importable in the backend environment. On Python versions Spark doesn't support
(e.g. 3.14) or JVM mismatches, it falls back to a **pandas/scikit-learn engine** that mirrors
every stage 1:1 — same casts, same scaler semantics (population std), same `seed=42`, same
decade aggregation — and reports the reason on the dashboard. The benchmark stage compares
the two execution styles for the same aggregation.

To enable Spark on this machine, create a Python 3.11–3.13 environment with `pyspark` and
Java 17/21 installed, then point the backend at that interpreter.

## Tests

```bash
cd backend
.venv/Scripts/python -m pytest tests -q
```

Covers: cleaning/casting fixes (decimal years, malformed rows), feature-matrix standardization,
full engine results contract (shares sum to 100%, silhouette bounds), API run lifecycle,
track filters, dataset year-range reporting, year-window clamping, notebook JSON validity
(nbformat 4, all sections, fixes present), and one test per BDA analysis — HDFS block
arithmetic, MapReduce job outputs and combiner savings, Bloom filter false-negative guarantee,
graph metric consistency, stream windows/drift thresholds, supervised metrics, EDA correlation
symmetry, and the core/additional concept split.

Tests are isolated: the API fixture points `VIBESHIFT_DATA_DIR` at a temp directory **and**
`VIBESHIFT_MONGO_DB` at `vibeshift_test`, so a test run can never leave broken entries in the
app's real run history. If registry documents and artifacts ever do drift apart, clean them up
with:

```bash
.venv/Scripts/python scripts/prune_runs.py           # dry run - lists stale documents
.venv/Scripts/python scripts/prune_runs.py --apply   # delete documents with no artifacts
```

## Notebook export

From any completed run, **Export .ipynb** downloads a Colab-ready notebook with:

1. Section-wise code (setup → ingestion → cleaning → MLlib preprocessing → clustering/PCA →
   aggregation → visualizations → benchmarking)
2. All transcript fixes: path auto-detection, `spark.sql.ansi.enabled=false`,
   double→int year casting, quote/escape CSV parsing, explicit feature casts + dropna
3. Your run's configuration (k, year range, features) injected
4. A markdown snapshot of the run's actual results (cluster table, decade × cluster shares,
   benchmark) for the mini-project report
