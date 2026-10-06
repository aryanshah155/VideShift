import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import Layout from '../components/Layout.jsx'
import Heatmap from '../components/Heatmap.jsx'
import StageConsole from '../components/StageConsole.jsx'
import Stat from '../components/Stat.jsx'
import BdaSuite from '../components/BdaSuite.jsx'
import { clusterColor } from '../components/ClusterBadge.jsx'
import { api } from '../api/client.js'
import { useRunPoll } from '../hooks/useRunPoll.js'

export default function RunResults() {
  const { runId } = useParams()
  const { status, error: pollError } = useRunPoll(runId)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (status?.state !== 'done') return undefined
    api
      .runResults(runId)
      .then(setResults)
      .catch((e) => setError(e.message))
    return undefined
  }, [runId, status?.state])

  if (pollError) return <Layout><p className="text-red-400">{pollError}</p></Layout>
  if (!status) return <Layout><p className="text-muted">Loading run…</p></Layout>

  if (status.state === 'failed')
    return (
      <Layout>
        <h1 className="text-2xl font-bold text-red-400">Run failed</h1>
        <pre className="mt-4 overflow-x-auto rounded-xl bg-panel p-4 font-mono text-xs text-red-300">
          {status.error}
          {'\n\n'}
          {status.traceback}
        </pre>
      </Layout>
    )

  if (status.state !== 'done')
    return (
      <Layout>
        <h1 className="text-2xl font-bold">
          Run <span className="font-mono text-accent">{runId}</span> is {status.state}…
        </h1>
        <div className="mt-6 max-w-2xl">
          <StageConsole stages={status.stages} />
        </div>
      </Layout>
    )

  if (!results) return <Layout><p className="text-muted">Loading results…</p></Layout>
  return <ResultsView runId={runId} status={status} results={results} />
}

function ResultsView({ runId, status, results }) {
  const cfg = status.config
  const decades = results.decades
  const clusters = results.clusters
  const clusterCols = useMemo(
    () => clusters.map((c) => ({ key: String(c.cluster), label: `C${c.cluster}` })),
    [clusters],
  )
  const heatRows = useMemo(
    () =>
      decades.map((d) => ({
        key: String(d.decade),
        label: `${d.decade}s`,
        cells: d.shares,
      })),
    [decades],
  )

  const trendFeats = ['energy', 'acousticness', 'valence', 'danceability'].filter((f) =>
    Object.keys(results.feature_trends).includes(f),
  )
  const trendData = useMemo(() => {
    const decadeKeys = Object.keys(results.feature_trends[trendFeats[0]] || {})
    return decadeKeys
      .map((d) => {
        const row = { decade: `${d}s` }
        for (const f of trendFeats) row[f] = results.feature_trends[f][d]
        return row
      })
      .sort((a, b) => a.decade.localeCompare(b.decade))
  }, [results.feature_trends, trendFeats])

  return (
    <Layout>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">Vibe-shift results</h1>
          <p className="mt-1 text-sm text-muted">
            Run <span className="font-mono text-accent">{runId}</span> · engine{' '}
            <span className="font-semibold text-zinc-200">{results.engine}</span> ·{' '}
            {results.rows_clean.toLocaleString()} clean rows · {results.total_seconds}s total
          </p>
        </div>
        <div className="flex gap-2">
          <Link className="btn-ghost" to={`/runs/${runId}/tracks`}>
            Track explorer
          </Link>
          <a className="btn-primary" href={api.notebookUrl(runId)}>
            ⬇ Export .ipynb
          </a>
        </div>
      </div>

      {/* Stat strip */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Tracks clustered" value={results.rows_clean.toLocaleString()} />
        <Stat label="Clusters (k)" value={String(results.best_k ?? cfg.k)} sub={results.best_k ? 'auto-selected' : undefined} />
        <Stat
          label="Silhouette"
          value={results.silhouette != null ? results.silhouette.toFixed(3) : '—'}
        />
        <Stat label="Inertia" value={results.inertia != null ? Math.round(results.inertia).toLocaleString() : '—'} />
      </div>

      {/* The money chart */}
      <section className="card mb-6">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="font-bold">Historical vibe shift — decade × cluster</h2>
          <span className="text-xs text-muted">% of each decade&apos;s tracks in each acoustic cluster</span>
        </div>
        <Heatmap
          rowLabel="Decade"
          colLabel="Cluster"
          rows={heatRows}
          columns={clusterCols}
          valueFmt={(v) => v.toFixed(1)}
          legend="Reading: each row sums to 100%. Watch acoustic profiles decay and high-energy profiles rise across decades."
        />
      </section>

      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        {/* Cluster profiles */}
        <section className="card">
          <h2 className="mb-3 font-bold">Cluster profiles — mean feature values</h2>
          <Heatmap
            rowLabel="Cluster"
            colLabel="Feature"
            rows={clusters.map((c) => ({
              key: String(c.cluster),
              label: `${c.cluster} · ${c.label}`,
              cells: c.means,
            }))}
            columns={Object.keys(clusters[0]?.means || {}).map((f) => ({ key: f, label: f.slice(0, 6) }))}
            valueFmt={(v) => v.toFixed(2)}
            legend={`Cluster sizes: ${clusters.map((c) => `C${c.cluster} ${c.share_pct.toFixed(1)}%`).join(' · ')}`}
          />
        </section>

        {/* Cluster sizes */}
        <section className="card">
          <h2 className="mb-3 font-bold">Cluster sizes</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={clusters.map((c) => ({ name: `C${c.cluster}`, size: c.size }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2a26" />
              <XAxis dataKey="name" stroke="#8b9a94" />
              <YAxis stroke="#8b9a94" />
              <Tooltip
                contentStyle={{ background: '#121715', border: '1px solid #1f2a26', borderRadius: 8 }}
              />
              <Bar dataKey="size" radius={[6, 6, 0, 0]}>
                {clusters.map((c) => (
                  <Cell key={c.cluster} fill={clusterColor(c.cluster)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </section>
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        {/* PCA scatter */}
        <section className="card">
          <h2 className="mb-3 font-bold">PCA map (2D projection of scaled features)</h2>
          <ResponsiveContainer width="100%" height={320}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2a26" />
              <XAxis type="number" dataKey="x" name="PC1" stroke="#8b9a94" hide />
              <YAxis type="number" dataKey="y" name="PC2" stroke="#8b9a94" hide />
              <ZAxis range={[18, 18]} />
              <Tooltip
                contentStyle={{ background: '#121715', border: '1px solid #1f2a26', borderRadius: 8 }}
                formatter={(v, name) => (name === 'name' ? v : typeof v === 'number' ? v.toFixed(2) : v)}
              />
              <Scatter data={results.pca_sample} isAnimationActive={false}>
                {results.pca_sample.map((p, i) => (
                  <Cell key={i} fill={clusterColor(p.cluster)} fillOpacity={0.75} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </section>

        {/* Trend lines */}
        <section className="card">
          <h2 className="mb-3 font-bold">Decade trends — mean feature values</h2>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2a26" />
              <XAxis dataKey="decade" stroke="#8b9a94" />
              <YAxis stroke="#8b9a94" domain={[0, 'auto']} />
              <Tooltip
                contentStyle={{ background: '#121715', border: '1px solid #1f2a26', borderRadius: 8 }}
              />
              {trendFeats.map((f) => (
                <Line key={f} type="monotone" dataKey={f} stroke={TREND_COLORS[f]} strokeWidth={2} dot={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </section>
      </div>

      {/* Big Data Analytics suite: Exp.1-Exp.8 + stream processing */}
      {results.bda && Object.keys(results.bda).length > 0 && <BdaSuite bda={results.bda} />}

      {/* Silhouette sweep */}
      {Object.keys(results.silhouette_by_k || {}).length > 0 && (
        <section className="card mb-6">
          <h2 className="mb-3 font-bold">
            Best-k sweep (silhouette) — selected k={results.best_k}
          </h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={Object.entries(results.silhouette_by_k).map(([k, v]) => ({ k: `k=${k}`, sil: v }))}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2a26" />
              <XAxis dataKey="k" stroke="#8b9a94" />
              <YAxis stroke="#8b9a94" />
              <Tooltip
                contentStyle={{ background: '#121715', border: '1px solid #1f2a26', borderRadius: 8 }}
              />
              <Bar dataKey="sil" fill="#1ed760" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </section>
      )}

      {/* Benchmark */}
      {results.benchmark && (
        <section className="card mb-6">
          <h2 className="mb-3 font-bold">Execution benchmark</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat label={results.benchmark.label_a} value={`${results.benchmark.seconds_a}s`} />
            <Stat label={results.benchmark.label_b} value={`${results.benchmark.seconds_b}s`} />
            <Stat label="Speedup" value={`${results.benchmark.speedup}×`} accent />
          </div>
          <p className="mt-3 text-xs text-muted">{results.benchmark.note}</p>
        </section>
      )}
    </Layout>
  )
}

const TREND_COLORS = {
  danceability: '#1ed760',
  energy: '#f59e0b',
  valence: '#4f9cf9',
  acousticness: '#ec4899',
  instrumentalness: '#8b5cf6',
  loudness: '#14b8a6',
  speechiness: '#eab308',
  tempo: '#94a3b8',
}
