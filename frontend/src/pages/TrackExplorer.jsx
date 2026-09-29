import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Layout from '../components/Layout.jsx'
import { clusterColor } from '../components/ClusterBadge.jsx'
import { api } from '../api/client.js'

export default function TrackExplorer() {
  const { runId } = useParams()
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [cluster, setCluster] = useState('')
  const [decade, setDecade] = useState('')
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const pageSize = 50

  useEffect(() => {
    api.runResults(runId).then(setResults).catch(() => {})
  }, [runId])

  useEffect(() => {
    let live = true
    setError(null)
    api
      .runTracks(runId, { search, cluster, decade, page, pageSize })
      .then((d) => {
        if (live) setData(d)
      })
      .catch((e) => {
        if (live) setError(e.message)
      })
    return () => {
      live = false
    }
  }, [runId, search, cluster, decade, page])

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  const clusterOptions = results?.clusters?.map((c) => (
    <option key={c.cluster} value={c.cluster}>
      C{c.cluster} · {c.label}
    </option>
  ))

  return (
    <Layout>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">Track explorer</h1>
          <p className="mt-1 text-sm text-muted">
            Cluster assignments per track for run{' '}
            <span className="font-mono text-accent">{runId}</span>
          </p>
        </div>
        <Link className="btn-ghost" to={`/runs/${runId}`}>← Results</Link>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_auto_auto]">
        <input
          className="input"
          placeholder="Search track or artist…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
        <select
          className="input"
          value={cluster}
          onChange={(e) => {
            setCluster(e.target.value)
            setPage(1)
          }}
        >
          <option value="">All clusters</option>
          {clusterOptions}
        </select>
        <select
          className="input"
          value={decade}
          onChange={(e) => {
            setDecade(e.target.value)
            setPage(1)
          }}
        >
          <option value="">All decades</option>
          {(results?.decades || []).map((d) => (
            <option key={d.decade} value={d.decade}>
              {d.decade}s
            </option>
          ))}
        </select>
      </div>

      {error && <p className="mb-4 text-sm text-red-400">{error}</p>}

      <div className="card !p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-edge text-left text-xs uppercase tracking-wider text-muted">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Track</th>
                <th className="px-4 py-3">Artist(s)</th>
                <th className="px-4 py-3">Year</th>
                <th className="px-4 py-3">Decade</th>
                <th className="px-4 py-3">Cluster</th>
              </tr>
            </thead>
            <tbody>
              {(data?.tracks || []).map((t, i) => (
                <tr key={t.id} className="border-b border-edge/40 hover:bg-white/[0.02]">
                  <td className="px-4 py-2 font-mono text-xs text-muted">
                    {(data.page - 1) * data.page_size + i + 1}
                  </td>
                  <td className="max-w-[280px] truncate px-4 py-2 font-medium">{t.name}</td>
                  <td className="max-w-[200px] truncate px-4 py-2 text-muted">{t.artists}</td>
                  <td className="px-4 py-2 text-muted">{t.year ?? '—'}</td>
                  <td className="px-4 py-2 text-muted">{t.decade ? `${t.decade}s` : '—'}</td>
                  <td className="px-4 py-2">
                    <span
                      className="badge border-transparent font-bold"
                      style={{ background: `${clusterColor(t.cluster)}22`, color: clusterColor(t.cluster) }}
                    >
                      C{t.cluster}
                    </span>
                  </td>
                </tr>
              ))}
              {data && data.tracks.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-muted">
                    No tracks match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between text-sm text-muted">
        <span>
          {data ? `${data.total.toLocaleString()} tracks` : '…'} · page {data?.page ?? '—'} / {totalPages}
        </span>
        <div className="flex gap-2">
          <button className="btn-ghost !px-3 !py-1" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            ← Prev
          </button>
          <button
            className="btn-ghost !px-3 !py-1"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next →
          </button>
        </div>
      </div>
    </Layout>
  )
}
