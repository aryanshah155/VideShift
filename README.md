# VibeShift — Spotify "Vibe Shift" Acoustic Clustering

A full-stack analytics app that quantifies historical **vibe shifts** in popular music:
distributed K-Means clustering + PCA over Spotify audio features (danceability, energy,
valence, tempo, acousticness, …), aggregated by release decade into interactive heatmaps.

Built from a Big Data Analytics mini-project Colab notebook (PySpark MLlib pipeline over
the Spotify 1.2M+ Songs dataset), turned into a production-style app with a Python backend
and a React dashboard — following the planning methodology of
[gstack](https://github.com/garrytan/gstack) (see [docs/gstack-methodology.md](docs/gstack-methodology.md)).

## Features

- **Dashboard** — dataset status, engine badge (PySpark vs pandas fallback), run configuration
  (k, year range, feature toggles, best-k silhouette sweep, row sampling), live stage console
  with per-stage timings, and run history.
- **Results** — the vibe-shift heatmap (decade × cluster shares), cluster-profile heatmap,
  PCA scatter (2D projection), decade trend lines, cluster sizes, silhouette sweep, and the
  execution benchmark card.
- **Track explorer** — search + cluster/decade filters over every track's cluster assignment.
- **Notebook export** — one-click section-wise `.ipynb` reproducing the Colab pipeline with all
  the debugging fixes baked in, plus a markdown snapshot of the run's actual results.

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
│       ├── notebook_export.py  # .ipynb generator
│       ├── store.py            # Mongo store + JSON fallback
│       ├── routers/            # runs, dataset, notebook endpoints
│       ├── pipeline/
│       │   ├── ingest.py       # CSV/Parquet loading, dataset status
│       │   ├── prepare.py      # cleaning, casting, decade, scaling
│       │   ├── pandas_engine.py# single-node engine (sklearn)
│       │   ├── spark_engine.py # PySpark MLlib engine
│       │   ├── engines.py      # engine detection/selection
│       │   ├── runner.py       # threaded job runner
│       │   └── tracks.py       # per-run Parquet track store
│       └── tests/              # pytest suite
└── frontend/
    └── src/                    # Vite + React 18 + Tailwind + Recharts
```

**API**: `POST /api/runs` · `GET /api/runs` · `GET /api/runs/{id}` ·
`GET /api/runs/{id}/results` · `GET /api/runs/{id}/tracks?search&cluster&decade&page` ·
`GET /api/runs/{id}/notebook` · `GET /api/dataset/status` · `GET /api/engine` · `GET /api/store`

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
pca → aggregate → benchmark live.

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
track filters, notebook JSON validity (nbformat 4, all sections, fixes present).

## Notebook export

From any completed run, **Export .ipynb** downloads a Colab-ready notebook with:

1. Section-wise code (setup → ingestion → cleaning → MLlib preprocessing → clustering/PCA →
   aggregation → visualizations → benchmarking)
2. All transcript fixes: path auto-detection, `spark.sql.ansi.enabled=false`,
   double→int year casting, quote/escape CSV parsing, explicit feature casts + dropna
3. Your run's configuration (k, year range, features) injected
4. A markdown snapshot of the run's actual results (cluster table, decade × cluster shares,
   benchmark) for the mini-project report
