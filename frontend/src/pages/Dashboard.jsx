import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Layout from '../components/Layout.jsx'
import StageConsole from '../components/StageConsole.jsx'
import Stat from '../components/Stat.jsx'
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

/** Rows in a closed [from, to] year window, estimated from the decade histogram. */
function estimateRows(decadeCounts, from, to) {
  if (!decadeCounts) return null
  let total = 0
  for (const [decade, count] of Object.entries(decadeCounts)) {
    const start = Number(decade)
    const end = start + 9
    if (end >= from && start <= to) {
      // Pro-rate the boundary decades instead of counting them whole.
      const overlapFrom = Math.max(start, from)
      const overlapTo = Math.min(end, to)
      const overlap = overlapTo - overlapFrom + 1
      total += (count * overlap) / 10
    }
  }
  return Math.round(total)
}

export default function Dashboard() {
  const nav = useNavigate()
  const [dataset, setDataset] = useState(null)
  const [engine, setEngine] = useState(null)
  const [store, setStore] = useState('')
  const [runs, setRuns] = useState([])
  const [concepts, setConcepts] = useState(null)
  const [yearsTouched, setYearsTouched] = useState(false)
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
  const [active, setActive] = useState(null)
  const pollRef = useRef(null)

  const loadMeta = useCallback(() => {
    api.datasetStatus().then(setDataset).catch((e) => setError(e.message))
    api.engineStatus().then(setEngine).catch(() => {})
    api.storeInfo().then((s) => setStore(s.backend)).catch(() => {})
    api.listRuns(12).then(setRuns).catch(() => {})
    api.concepts().then(setConcepts).catch(() => {})
  }, [])

  useEffect(() => {
    loadMeta()
  }, [loadMeta])

  useEffect(() => () => clearInterval(pollRef.current), [])

  // ---- Year bounds come from the dataset itself ------------------------ #
  const yearMin = dataset?.year_min ?? 1900
  const yearMax = dataset?.year_max ?? new Date().getFullYear()
  const robustFrom = dataset?.year_p01 ?? yearMin
  const robustTo = dataset?.year_p99 ?? yearMax

  // Seed the window from the dataset's robust range until the user edits it.
  useEffect(() => {
    if (!dataset?.found || yearsTouched) return
    setConfig((c) => ({ ...c, year_from: robustFrom, year_to: robustTo }))
  }, [dataset?.found, yearsTouched, robustFrom, robustTo])

  const yearError = useMemo(() => {
    if (!dataset?.found) return null
    if (config.year_from < yearMin || config.year_to > yearMax)
      return `Dataset covers ${yearMin}–${yearMax}.`
    if (config.year_from > config.year_to) return '“Year from” must not exceed “Year to”.'
    return null
  }, [dataset?.found, config.year_from, config.year_to, yearMin, yearMax])

  const estimatedRows = useMemo(
    () => estimateRows(dataset?.decade_counts, config.year_from, config.year_to),
    [dataset?.decade_counts, config.year_from, config.year_to],
  )

  const setYear = (key, raw) => {
    setYearsTouched(true)
    if (raw === '') return
    setConfig((c) => ({ ...c, [key]: Number(raw) }))
  }

  const normalizeYear = (key) => {
    setConfig((c) => {
      const clamped = Math.min(yearMax, Math.max(yearMin, Math.round(c[key])))
      const next = { ...c, [key]: clamped }
      if (next.year_from > next.year_to) {
        if (key === 'year_from') next.year_to = clamped
        else next.year_from = clamped
      }
      return next
    })
  }

  const applyRange = (from, to) => {
    setYearsTouched(true)
    setConfig((c) => ({ ...c, year_from: from, year_to: to }))
  }

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

  return (
    <Layout>
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold tracking-tight">
          Historical <span className="text-accent">vibe shifts</span> in popular music
        </h1>
        <p className="mt-1 text-muted">
          Distributed K-Means + PCA over Spotify audio features — clustered acoustic profiles,
          aggregated by decade, with the full Big Data Analytics lab applied on top.
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* BDA coverage strip */}
      {concepts && (
        <section className="card mb-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-muted">
                Big Data Analytics — core portion
              </h2>
              <p className="mt-1 text-sm">
                <span className="font-bold text-accent">
                  {concepts.coverage.core_concepts ?? '—'} concepts
                </span>{' '}
                from the CSC702 lab manual:{' '}
                <span className="font-semibold text-zinc-200">
                  {concepts.core?.title ?? 'MapReduce · NoSQL · Visualization'}
                </span>
                . A further{' '}
                <span className="font-semibold">{concepts.coverage.additional_concepts ?? 0}</span>{' '}
                concepts run as additional analysis.
                {concepts.has_run && (
                  <span className="text-muted">
                    {' '}
                    · evidence from run{' '}
                    <span className="font-mono text-zinc-300">{concepts.run_id}</span>
                  </span>
                )}
              </p>
            </div>
            <Link className="btn-ghost !py-1.5 text-xs" to="/concepts">
              Explore all concepts →
            </Link>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {concepts.experiments.map((exp) => {
              const count = concepts.concepts.filter((c) => c.experiment === exp.id).length
              if (!count) return null
              return (
                <span
                  key={exp.id}
                  className={`badge ${exp.core ? 'border-accent/60 text-accent' : 'border-edge text-muted'}`}
                  title={exp.title}
                >
                  {exp.id} · {count}
                  {exp.core ? ' ★' : ''}
                </span>
              )
            })}
          </div>
        </section>
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
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="font-bold">{dataset.size_mb} MB</span>{' '}
                    <span className="text-muted">on disk</span>
                  </div>
                  <div>
                    <span className="font-bold">
                      {dataset.rows ? dataset.rows.toLocaleString() : '—'}
                    </span>{' '}
                    <span className="text-muted">rows</span>
                  </div>
                  <div>
                    <span className="font-bold">{dataset.columns ?? '—'}</span>{' '}
                    <span className="text-muted">columns</span>
                  </div>
                  <div>
                    <span className="font-bold">
                      {dataset.year_min != null ? `${dataset.year_min}–${dataset.year_max}` : '—'}
                    </span>{' '}
                    <span className="text-muted">years</span>
                  </div>
                </div>
                {dataset.decade_counts && Object.keys(dataset.decade_counts).length > 0 && (
                  <div className="mt-4">
                    <p className="label mb-1">Tracks per decade</p>
                    <DecadeBars counts={dataset.decade_counts} />
                  </div>
                )}
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
            <h2 className="mb-4 text-sm font-bold uppercase tracking-wider text-muted">
              Run configuration
            </h2>
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
                    min={yearMin}
                    max={yearMax}
                    value={config.year_from}
                    onChange={(e) => setYear('year_from', e.target.value)}
                    onBlur={() => normalizeYear('year_from')}
                  />
                </div>
                <div>
                  <label className="label">Year to</label>
                  <input
                    className="input"
                    type="number"
                    min={yearMin}
                    max={yearMax}
                    value={config.year_to}
                    onChange={(e) => setYear('year_to', e.target.value)}
                    onBlur={() => normalizeYear('year_to')}
                  />
                </div>
              </div>

              {dataset?.found && (
                <div className="rounded-lg border border-edge/70 bg-base/60 px-3 py-2 text-xs">
                  <p className="text-muted">
                    Bounds from the dataset:{' '}
                    <span className="font-mono text-zinc-300">
                      min {yearMin} · max {yearMax}
                    </span>
                    {' · '}
                    <span className="text-zinc-400">
                      99% of tracks inside {robustFrom}–{robustTo}
                    </span>
                  </p>
                  {estimatedRows != null && !yearError && (
                    <p className="mt-1 text-muted">
                      Selected window covers ≈{' '}
                      <span className="font-semibold text-accent">
                        {estimatedRows.toLocaleString()}
                      </span>{' '}
                      of {dataset.rows ? dataset.rows.toLocaleString() : '?'} tracks
                    </p>
                  )}
                  {yearError && <p className="mt-1 text-amber-400">{yearError}</p>}
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      className="btn-ghost !px-2 !py-0.5 !text-[11px]"
                      onClick={() => applyRange(yearMin, yearMax)}
                    >
                      Full range
                    </button>
                    <button
                      type="button"
                      className="btn-ghost !px-2 !py-0.5 !text-[11px]"
                      onClick={() => applyRange(robustFrom, robustTo)}
                    >
                      99% range
                    </button>
                  </div>
                </div>
              )}

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
                    >
                      {f}
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
                disabled={submitting || !dataset?.found || !!yearError}
                onClick={startRun}
              >
                {submitting ? 'Starting…' : '▶ Run pipeline'}
              </button>
              {!dataset?.found && (
                <p className="text-center text-xs text-muted">Add the dataset to enable runs</p>
              )}
              {dataset?.found && yearError && (
                <p className="text-center text-xs text-amber-400">{yearError}</p>
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
                        <td className="py-2 text-xs">
                          {r.results_summary?.rows_clean?.toLocaleString() ?? '—'}
                        </td>
                        <td className="py-2 text-xs">
                          {r.results_summary?.silhouette?.toFixed(3) ?? '—'}
                        </td>
                        <td className="py-2 text-xs">
                          {r.results_summary?.total_seconds != null
                            ? `${r.results_summary.total_seconds}s`
                            : '—'}
                        </td>
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
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wider text-muted">
              About the pipeline
            </h2>
            <p className="text-sm leading-relaxed text-muted">
              Each run executes the Colab stages — fault-tolerant CSV ingest → safe casting + decade
              engineering → VectorAssembler + StandardScaler (mean 0, std 1) → K-Means (seed 42) with
              optional silhouette sweep → PCA to 2D → decade × cluster aggregation — and then layers
              the Big Data Analytics suite on the clustered result. The core portion is{' '}
              <span className="text-zinc-300">MapReduce</span> (word count, aggregates, map-side
              join, top-N sorting, inverted index),{' '}
              <span className="text-zinc-300">NoSQL persistence</span> in MongoDB seen through a
              live read-only command console, and{' '}
              <span className="text-zinc-300">data visualization</span> through the decade × cluster
              dashboards and correlation statistics. HDFS modelling, the Bloom filter index, network
              community detection, stream windows and supervised ML additionally run on every run
              and are available under “additional analyses”.
            </p>
          </section>
        </div>
      </div>
    </Layout>
  )
}

/** Compact decade histogram built from CSS only. */
function DecadeBars({ counts }) {
  const entries = Object.entries(counts).sort((a, b) => Number(a[0]) - Number(b[0]))
  const max = Math.max(...entries.map(([, c]) => c), 1)
  return (
    <div className="flex h-16 items-end gap-[3px]">
      {entries.map(([decade, count]) => (
        <div
          key={decade}
          className="group relative flex-1 rounded-sm bg-accent/70 transition hover:bg-accent"
          style={{ height: `${Math.max(4, (count / max) * 100)}%` }}
          title={`${decade}s: ${count.toLocaleString()} tracks`}
        />
      ))}
    </div>
  )
}
