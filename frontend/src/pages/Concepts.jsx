import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Layout from '../components/Layout.jsx'
import Stat from '../components/Stat.jsx'
import { api } from '../api/client.js'

export default function Concepts() {
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState(null)
  const [runs, setRuns] = useState([])
  const [error, setError] = useState(null)
  const [category, setCategory] = useState('')
  const [showAdditional, setShowAdditional] = useState(false)
  const runId = params.get('run') || ''

  const load = useCallback(() => {
    api
      .concepts(runId || undefined)
      .then(setData)
      .catch((e) => setError(e.message))
    api.listRuns(25).then(setRuns).catch(() => {})
  }, [runId])

  useEffect(() => {
    load()
  }, [load])

  const doneRuns = useMemo(() => runs.filter((r) => r.state === 'done'), [runs])

  const grouped = useMemo(() => {
    if (!data) return []
    const filtered = category
      ? data.concepts.filter((c) => c.category === category)
      : data.concepts
    return data.experiments
      .map((exp) => ({
        ...exp,
        concepts: filtered.filter((c) => c.experiment === exp.id),
      }))
      .filter((exp) => exp.concepts.length > 0)
  }, [data, category])

  // The mini-project portion is surfaced first; the rest stays available but is
  // collapsed so the core deliverable is what a reviewer sees immediately.
  const coreGroups = grouped.filter((g) => g.concepts[0].primary)
  const additionalGroups = grouped.filter((g) => !g.concepts[0].primary)
  const coreRows = data?.concepts.filter((c) => c.primary) ?? []
  const additionalRows = data?.concepts.filter((c) => !c.primary) ?? []

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold tracking-tight">
          Big Data <span className="text-accent">Analytics concepts</span>
        </h1>
        <p className="mt-1 max-w-3xl text-muted">
          Every technique in this project, mapped to the CSC702 (Big Data Analysis) lab manual —
          with the live number each one produced in the last pipeline run, and where in the results
          payload the evidence lives.
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {data && (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
            <Stat
              label="Core concepts"
              value={data.coverage.core_concepts ?? coreRows.length}
              sub={data.core?.title}
              accent
            />
            <Stat
              label="Core experiments"
              value={(data.core?.experiments || []).join(' · ')}
              sub="MapReduce · NoSQL · Visualization"
            />
            <Stat
              label="Core evidence"
              value={`${data.coverage.core_with_evidence ?? 0}/${data.coverage.core_concepts ?? 0}`}
              sub={data.has_run ? `from run ${data.run_id}` : 'run the pipeline to attach evidence'}
            />
            <Stat
              label="Additional analyses"
              value={data.coverage.additional_concepts ?? additionalRows.length}
              sub={`${data.coverage.experiments} experiments in total, all executed`}
            />
          </div>

          {data.core?.why && (
            <p className="mb-6 rounded-xl border border-accent/30 bg-accent/5 px-4 py-3 text-sm text-zinc-300">
              <span className="font-semibold text-accent">Why these three: </span>
              {data.core.why}
            </p>
          )}

          <div className="card mb-6 flex flex-wrap items-center gap-3">
            <label className="label !mb-0">Evidence from run</label>
            <select
              className="input max-w-xs"
              value={runId}
              onChange={(e) => {
                const value = e.target.value
                if (value) setParams({ run: value })
                else setParams({})
              }}
            >
              <option value="">Latest completed run{data.has_run ? ` (${data.run_id})` : ''}</option>
              {doneRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.id} · k={r.config?.k} · {r.results_summary?.rows_clean?.toLocaleString() ?? '?'} rows
                </option>
              ))}
            </select>
            {data.run_id && (
              <Link className="btn-ghost !py-1.5 text-xs" to={`/runs/${data.run_id}`}>
                Open run results →
              </Link>
            )}
            {!data.has_run && (
              <span className="text-xs text-amber-300">
                No completed run yet — metrics stay blank until you launch the pipeline.
              </span>
            )}
          </div>

          <div className="mb-6 flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setCategory('')}
              className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                category === '' ? 'border-accent bg-accent/10 text-accent' : 'border-edge text-muted hover:text-zinc-200'
              }`}
            >
              All categories ({data.concepts.length})
            </button>
            {data.categories.map((c) => (
              <button
                key={c.category}
                type="button"
                onClick={() => setCategory(c.category)}
                className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                  category === c.category
                    ? 'border-accent bg-accent/10 text-accent'
                    : 'border-edge text-muted hover:text-zinc-200'
                }`}
              >
                {c.category} ({c.count})
              </button>
            ))}
          </div>

          <h2 className="mb-4 text-xl font-extrabold tracking-tight">
            Core portion <span className="text-accent">(this project's scope)</span>
          </h2>
          <div className="space-y-6">
            {coreGroups.map((exp) => (
              <ConceptGroup key={exp.id} exp={exp} />
            ))}
          </div>

          {additionalGroups.length > 0 && (
            <>
              <button
                type="button"
                onClick={() => setShowAdditional((v) => !v)}
                className="btn-ghost mt-8"
              >
                {showAdditional
                  ? 'Hide additional analyses'
                  : `Show ${additionalRows.length} additional concepts (${additionalGroups
                      .map((g) => g.id)
                      .join(' · ')})`}
              </button>

              {showAdditional && (
                <div className="mt-4 space-y-6 opacity-90">
                  <p className="text-xs text-muted">
                    Implemented and executed on every run, but kept outside the core portion so
                    the selected three stay front and centre.
                  </p>
                  {additionalGroups.map((exp) => (
                    <ConceptGroup key={exp.id} exp={exp} />
                  ))}
                </div>
              )}
            </>
          )}

          <section className="card mt-8">
            <h2 className="mb-2 font-bold">How the core three satisfy the manual</h2>
            <p className="text-sm leading-relaxed text-muted">
              All three selected concepts run on the real 1.2M-track Spotify corpus, not a toy
              dataset, and all three are exercised inside a single pipeline run:
            </p>
            <ul className="mt-3 space-y-2 text-sm leading-relaxed text-muted">
              <li>
                <span className="font-semibold text-zinc-200">MapReduce (Exp.4 / Exp.5)</span> — an
                in-process runtime with genuine map → partition → combine → shuffle → reduce phases,
                each timed and counted, running the manual's full exercise list: word count over
                track titles, per-decade aggregates with combiner savings, a map-side broadcast
                join against the cluster table, top-N sorting of artists, and an inverted index for
                searching.
              </li>
              <li>
                <span className="font-semibold text-zinc-200">
                  NoSQL with MongoDB (Exp.3)
                </span>{' '}
                — every run is persisted as a schemaless nested document (config, stage array,
                results summary) with a JSON-file fallback, and 26 mongosh commands are documented
                with live results: CRUD, nested-field and array queries, $lt/$gt comparison and the
                $group aggregation pipeline.
              </li>
              <li>
                <span className="font-semibold text-zinc-200">
                  Data visualization (Exp.8)
                </span>{' '}
                — interactive dashboards for the decade × cluster vibe-shift heatmap, cluster
                profiles, PCA scatter and decade trend lines, backed by descriptive statistics, a
                Pearson correlation heatmap and IQR / IsolationForest outlier detection.
              </li>
            </ul>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              The remaining experiments (HDFS, Bloom filter, network analysis, stream windows,
              supervised ML) are implemented and still execute on every run — they are presented as
              additional analysis above, not deleted, so the project can grow later without
              rewriting anything.
            </p>
          </section>
        </>
      )}

      {!data && !error && <p className="text-muted">Loading concept registry…</p>}
    </Layout>
  )
}

function ConceptGroup({ exp }) {
  return (
    <section>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2 border-b border-edge/60 pb-2">
        <h2 className="text-lg font-bold">
          <span className="text-accent">{exp.id}</span> · {exp.title}
        </h2>
        <span className="text-xs text-muted">{exp.co_lo}</span>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {exp.concepts.map((c) => (
          <article key={c.id} className="card !p-4">
            <div className="mb-2 flex items-start justify-between gap-2">
              <h3 className="text-sm font-bold leading-snug">{c.name}</h3>
              <span className="badge shrink-0 border-edge text-[10px] text-muted">
                {c.category}
              </span>
            </div>
            <p className="text-xs leading-relaxed text-muted">{c.summary}</p>
            <p className="mt-2 text-xs leading-relaxed text-zinc-400">
              <span className="font-semibold text-zinc-300">In this project: </span>
              {c.how}
            </p>
            <div
              className={`mt-3 rounded-lg border px-3 py-2 ${
                c.has_evidence
                  ? 'border-accent/30 bg-accent/5'
                  : 'border-amber-500/30 bg-amber-500/5'
              }`}
            >
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">
                Live evidence
              </p>
              <p
                className={`mt-0.5 font-mono text-xs ${c.has_evidence ? 'text-accent' : 'text-amber-300'}`}
              >
                {c.has_evidence ? c.metric : 'no evidence in this run'}
              </p>
            </div>
            <p className="mt-2 font-mono text-[10px] text-muted">{c.evidence}</p>
          </article>
        ))}
      </div>
    </section>
  )
}
