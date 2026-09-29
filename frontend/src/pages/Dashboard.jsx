import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Layout from '../components/Layout.jsx'
import StageConsole from '../components/StageConsole.jsx'
import { api } from '../api/client.js'

const ALL_FEATURES = [
  'danceability',
  'energy',
  'valence',
  'tempo',
  'acousticness',
  'instrumentalness',
  'loudness',
  'speechiness',
]

export default function Dashboard() {
  const nav = useNavigate()
  const [dataset, setDataset] = useState(null)
  const [engine, setEngine] = useState(null)
  const [store, setStore] = useState('')
  const [runs, setRuns] = useState([])
  const [config, setConfig] = useState({
    k: 5,
    year_from: 1960,
    year_to: 2023,
    features: ALL_FEATURES,
    find_best_k: false,
    sample_fraction: 1.0,
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const pollRef = useRef(null)

  const loadMeta = useCallback(() => {
    api.datasetStatus().then(setDataset).catch((e) => setError(e.message))
    api.engineStatus().then(setEngine).catch(() => {})
    api.storeInfo().then((s) => setStore(s.backend)).catch(() => {})
    api.listRuns(12).then(setRuns).catch(() => {})
  }, [])

  useEffect(() => {
    loadMeta()
  }, [loadMeta])

  useEffect(() => () => clearInterval(pollRef.current), [])

  const toggleFeature = (f) =>
    setConfig((c) => ({
      ...c,
      features: c.features.includes(f)
        ? c.features.filter((x) => x !== f)
        : [...c.features, f],
    }))

  const startRun = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const { id } = await api.createRun(config)
      // Follow the new run in the mini console
      const follow = async () => {
        const s = await api.runStatus(id)
        setActive(s)
        if (s.state === 'running') pollRef.current = setTimeout(follow, 1200)
        else {
          loadMeta()
          if (s.state === 'done') setTimeout(() => nav(`/runs/${id}`), 600)
        }
      }
      setActive({ id, state: 'running' })
      follow()
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const [active, setActive] = useState(null)

  return (
    <Layout>
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold tracking-tight">
          Historical <span className="text-accent">vibe shifts</span> in popular music
        </h1>
        <p className="mt-1 text-muted">
          Distributed K-Means + PCA over Spotify audio features — clustered acoustic profiles, aggregated by decade.
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left column: config + status cards */}
        <div className="space-y-6">
          <section className="card">
            <h2 className="mb-4 text-sm font-bold uppercase tracking-wider text-muted">Dataset</h2>
            {!dataset ? (
              <p className="text-sm text-muted">Checking…</p>
            ) : dataset.found ? (
              <div>
                <p className="stat-value text-accent">Ready</p>
                <p className="mt-1 break-all font-mono text-xs text-muted">{dataset.path}</p>
                <p className="mt-2 text-sm">
                  <span className="font-bold">{dataset.size_mb} MB</span> on disk
                </p>
              </div>
              ) : (
              <div>
                <p className="stat-value text-amber-400">Not found</p>
                <p className="mt-2 text-sm text-muted">{dataset.message}</p>
                <p className="mt-2 text-xs text-zinc-400">
                  Download:{' '}
                  <a
                    className="text-accent underline"
                    href="https://www.kaggle.com/datasets/rodolfofigueroa/spotify-12m-songs"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Spotify 1.2M+ Songs on Kaggle
                  </a>{' '}
                  → place <code className="font-mono">tracks_features.csv</code> in{' '}
                  <code className="font-mono">backend/data/</code>.
                </p>
              </div>
            )}
          </section>

          <section className="card">
            <h2 className="mb-4 text-sm font-bold uppercase tracking-wider text-muted">Engine</h2>
            {engine ? (
              <div>
                <span
                  className={`badge ${engine.engine === 'spark' ? 'border-accent text-accent' : 'border-amber-500/50 text-amber-300'}`}
                >
                  {engine.engine === 'spark' ? 'PySpark MLlib' : 'pandas / sklearn fallback'}
                </span>
                <p className="mt-3 text-xs leading-relaxed text-muted">{engine.reason}</p>
              </div>
            ) : (
              <p className="text-sm text-muted">Checking…</p>
            )}
            <p className="mt-3 text-xs text-muted">
              Store: <span className="font-mono text-zinc-300">{store || '…'}</span>
            </p>
          </section>

          <section className="card">
            <h2 className="mb-4 text-sm font-bold uppercase tracking-wider text-muted">Run configuration</h2>
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="label">Clusters (k)</label>
                  <input
                    className="input"
                    type="number"
                    min={2}
                    max={12}
                    value={config.k}
                    onChange={(e) => setConfig({ ...config, k: +e.target.value })}
                  />
                </div>
                <div>
                  <label className="label">Year from</label>
                  <input
                    className="input"
                    type="number"
                    value={config.year_from}
                    onChange={(e) => setConfig({ ...config, year_from: +e.target.value })}
                  />
                </div>
                <div>
                  <label className="label">Year to</label>
                  <input
                    className="input"
                    type="number"
                    value={config.year_to}
                    onChange={(e) => setConfig({ ...config, year_to: +e.target.value })}
                  />
                </div>
              </div>
              <div>
                <label className="label">Features</label>
                <div className="flex flex-wrap gap-2">
                  {ALL_FEATURES.map((f) => (
                    <button
                      key={f}
                      type="button"
                      onClick={() => toggleFeature(f)}
                      className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                        config.features.includes(f)
                          ? 'border-accent bg-accent/10 text-accent'
                          : 'border-edge text-muted hover:text-zinc-200'
                      }`}
                    >                      {f}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={config.find_best_k}
                    onChange={(e) => setConfig({ ...config, find_best_k: e.target.checked })}
                    className="h-4 w-4 accent-[#1ed760]"
                  />
                  Find best k (silhouette sweep k=2–8)
                </label>
              </div>
              <div>
                <label className="label">
                  Sample fraction: {Math.round(config.sample_fraction * 100)}%
                </label>
                <input
                  type="range"
                  min={5}
                  max={100}
                  value={config.sample_fraction * 100}
                  onChange={(e) => setConfig({ ...config, sample_fraction: +e.target.value / 100 })}
                  className="w-full accent-[#1ed760]"
                />
              </div>
              <button
                className="btn-primary w-full"
                disabled={submitting || !dataset?.found}
                onClick={startRun}
              >
                {submitting ? 'Starting…' : '▶ Run pipeline'}
              </button>
              {!dataset?.found && (
                <p className="text-center text-xs text-muted">Add the dataset to enable runs</p>
              )}
            </div>
          </section>
        </div>

        {/* Middle/right: live run + history */}
        <div className="space-y-6 lg:col-span-2">
          {active && (
            <section className="card border-accent/40">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-sm font-bold uppercase tracking-wider text-muted">
                  Live run <span className="font-mono text-accent">{active.id}</span>
                </h2>
                <Link className="btn-ghost !py-1 text-xs" to={`/runs/${active.id}`}>
                  Open →
                </Link>
              </div>
              <StageConsole stages={active.stages} />
              {active.state === 'failed' && (
                <p className="mt-3 rounded-lg bg-red-500/10 p-3 font-mono text-xs text-red-300">
                  {active.error}
                </p>
              )}
            </section>
          )}

          <section className="card">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-bold uppercase tracking-wider text-muted">Run history</h2>
              <button className="btn-ghost !py-1 text-xs" onClick={loadMeta}>
                Refresh
              </button>
            </div>
            {runs.length === 0 ? (
              <p className="text-sm text-muted">No runs yet. Configure and launch the pipeline.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-muted">
                      <th className="pb-2">Run</th>
                      <th className="pb-2">Engine</th>
                      <th className="pb-2">k</th>
                      <th className="pb-2">Rows</th>
                      <th className="pb-2">Silhouette</th>
                      <th className="pb-2">Time</th>
                      <th className="pb-2">State</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((r) => (
                      <tr key={r.id} className="border-t border-edge/60">
                        <td className="py-2 font-mono text-xs">
                          <Link className="text-accent hover:underline" to={`/runs/${r.id}`}>
                            {r.id}
                          </Link>
                        </td>
                        <td className="py-2 text-xs">{r.engine}</td>
                        <td className="py-2 text-xs">{r.config?.k}</td>
                        <td className="py-2 text-xs">{r.results_summary?.rows_clean?.toLocaleString() ?? '—'}</td>
                        <td className="py-2 text-xs">{r.results_summary?.silhouette?.toFixed(3) ?? '—'}</td>
                        <td className="py-2 text-xs">{r.results_summary?.total_seconds != null ? `${r.results_summary.total_seconds}s` : '—'}</td>
                        <td className="py-2">
                          <span
                            className={`badge ${
                              r.state === 'done'
                                ? 'border-accent text-accent'
                                : r.state === 'failed'
                                  ? 'border-red-500 text-red-400'
                                  : 'border-amber-500 text-amber-300'
                            }`}
                          >
                            {r.state}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="card">
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wider text-muted">About the pipeline</h2>
            <p className="text-sm leading-relaxed text-muted">
              Each run executes the same stages as the Colab notebook: fault-tolerant CSV ingest → safe
              casting + decade engineering → VectorAssembler + StandardScaler (mean 0, std 1) → K-Means
              (seed 42) with optional silhouette sweep → PCA to 2D → decade × cluster share aggregation →
              execution benchmark. Every run is persisted with per-stage timings, and you can export a
              fixed, section-wise Colab notebook from the results page.
            </p>
          </section>
        </div>
      </div>
    </Layout>
  )
}
