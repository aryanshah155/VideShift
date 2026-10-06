import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import Heatmap from './Heatmap.jsx'
import Stat from './Stat.jsx'

const CHART_STYLE = { background: '#121715', border: '1px solid #1f2a26', borderRadius: 8 }
const AXIS = '#8b9a94'
const PALETTE = ['#1ed760', '#4f9cf9', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6', '#eab308', '#ef4444']

export function communityColor(i) {
  return `hsl(${(i * 67) % 360} 68% 58%)`
}

// The mini-project portion: MapReduce (Exp.4/5), NoSQL (Exp.3) and
// visualization (Exp.8). Everything else stays implemented but is presented as
// additional analysis so the core deliverable is unmistakable.
const CORE_TABS = [
  { id: 'mapreduce', label: 'Exp.4–5 · MapReduce' },
  { id: 'nosql', label: 'Exp.3 · MongoDB (NoSQL)' },
  { id: 'eda', label: 'Exp.8 · Statistics & visualization' },
]

const ADVANCED_TABS = [
  { id: 'hdfs', label: 'Exp.1 · HDFS' },
  { id: 'bloom', label: 'Exp.6 · Bloom filter' },
  { id: 'graph', label: 'Exp.7 · Network' },
  { id: 'streaming', label: 'CO4 · Streams' },
  { id: 'ml', label: 'Exp.2 · ML models' },
]

export default function BdaSuite({ bda }) {
  const [tab, setTab] = useState('mapreduce')
  const [showAdvanced, setShowAdvanced] = useState(false)
  if (!bda) return null

  const tabs = [...CORE_TABS, ...(showAdvanced ? ADVANCED_TABS : [])]

  return (
    <section className="card mb-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-bold">Big Data Analytics suite</h2>
          <p className="text-xs text-muted">
            Core portion: MapReduce · NoSQL persistence · Data visualization ·{' '}
            {bda.summary?.analyses_ok ?? 0}/{bda.summary?.analyses_total ?? 0} analyses executed in{' '}
            {bda.summary?.seconds ?? '—'}s
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setShowAdvanced((v) => !v)
            if (showAdvanced) setTab('mapreduce')
          }}
          className="btn-ghost !py-1 text-xs"
        >
          {showAdvanced ? 'Hide additional analyses' : 'Show additional analyses (5)'}
        </button>
      </div>

      <div className="mb-5 flex flex-wrap gap-1.5">
        {tabs.map((t) => {
          const advanced = ADVANCED_TABS.some((a) => a.id === t.id)
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                tab === t.id
                  ? 'border-accent bg-accent/10 text-accent'
                  : advanced
                    ? 'border-edge/60 text-muted/70 hover:text-zinc-300'
                    : 'border-edge text-muted hover:text-zinc-200'
              }`}
            >
              {t.label}
            </button>
          )
        })}
      </div>

      {tab === 'hdfs' && <HdfsPanel data={bda.hdfs} />}
      {tab === 'mapreduce' && <MapReducePanel data={bda.mapreduce} />}
      {tab === 'bloom' && <BloomPanel data={bda.bloom} />}
      {tab === 'graph' && <GraphPanel data={bda.graph} />}
      {tab === 'streaming' && <StreamingPanel data={bda.streaming} />}
      {tab === 'ml' && <MlPanel data={bda.ml} />}
      {tab === 'eda' && <EdaPanel data={bda.eda} />}
      {tab === 'nosql' && <NosqlPanel data={bda.nosql} />}
    </section>
  )
}

function Failed({ data }) {
  if (!data) return <p className="text-sm text-muted">Analysis not available for this run.</p>
  if (data.error)
    return (
      <p className="rounded-lg bg-amber-500/10 p-3 font-mono text-xs text-amber-300">
        {data.error}
      </p>
    )
  return null
}

function ConceptList({ items }) {
  if (!items?.length) return null
  return (
    <div className="mt-4 border-t border-edge/60 pt-3">
      <p className="label">Concepts exercised</p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((c) => (
          <span key={c} className="badge border-edge text-[11px] text-muted">
            {c}
          </span>
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ HDFS */
function HdfsPanel({ data }) {
  if (!data || data.error) return <Failed data={data} />
  const file = data.file
  const nn = data.namenode
  return (
    <div>
      <Failed data={data} />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="HDFS path" value={<span className="text-base">{file.name}</span>} sub={file.path} />
        <Stat label="Blocks" value={file.blocks} sub={`${file.block_size_mb} MB blocks`} />
        <Stat label="Replication" value={`${file.replication}×`} sub={`${file.stored_human} stored`} />
        <Stat label="NameNode" value={nn.safemode} sub={`${nn.live_datanodes} live DataNodes`} />
      </div>

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <div>
          <p className="label">NameNode block map</p>
          <div className="max-h-64 overflow-y-auto rounded-lg border border-edge/60">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-panel">
                <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
                  <th className="px-3 py-2">Block</th>
                  <th className="px-3 py-2">Size</th>
                  <th className="px-3 py-2">Replica locations</th>
                </tr>
              </thead>
              <tbody>
                {data.blocks_shown.map((b) => (
                  <tr key={b.id} className="border-t border-edge/40">
                    <td className="px-3 py-1.5 font-mono">blk_{b.id}</td>
                    <td className="px-3 py-1.5 text-muted">{b.size_mb} MB</td>
                    <td className="px-3 py-1.5">
                      <div className="flex flex-wrap gap-1">
                        {b.replicas.map((r) => (
                          <span
                            key={r.node + r.replica}
                            className="badge border-edge text-[10px]"
                            title={`${r.ip} ${r.rack}`}
                          >
                            {r.node} <span className="text-muted">{r.rack}</span>
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <p className="label">DataNode occupancy</p>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
                <th className="py-2">Node</th>
                <th className="py-2">Rack</th>
                <th className="py-2">Blocks</th>
                <th className="py-2">Stored</th>
                <th className="py-2">State</th>
              </tr>
            </thead>
            <tbody>
              {data.datanodes.map((n) => (
                <tr key={n.node} className="border-t border-edge/40">
                  <td className="py-1.5 font-mono">{n.node}</td>
                  <td className="py-1.5 text-muted">{n.rack}</td>
                  <td className="py-1.5">{n.blocks}</td>
                  <td className="py-1.5 text-muted">{n.stored_mb} MB</td>
                  <td className="py-1.5 text-accent">{n.state}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-muted">
            {file.rows?.toLocaleString()} rows × {file.columns} columns in the file; the analysed
            projection keeps {file.analyzed_columns}. Block size source: {file.block_size_source}.
          </p>
        </div>
      </div>

      <p className="label">hdfs shell transcript ({data.commands.length} commands)</p>
      <div className="max-h-80 space-y-1 overflow-y-auto rounded-lg border border-edge/60 p-3">
        {data.commands.map((c, i) => (
          <details key={i} className="rounded border border-edge/40 bg-base/60">
            <summary className="cursor-pointer px-2 py-1 font-mono text-xs text-accent">
              $ {c.cmd}
              <span className="ml-2 font-sans text-muted">— {c.purpose}</span>
            </summary>
            <pre className="overflow-x-auto px-2 pb-2 font-mono text-[11px] text-zinc-300">
              {c.output || '(no output)'}
            </pre>
          </details>
        ))}
      </div>
      <ConceptList items={data.concepts} />
    </div>
  )
}

/* --------------------------------------------------------- MapReduce */
function MapReducePanel({ data }) {
  const [active, setActive] = useState(0)
  if (!data || data.error) return <Failed data={data} />
  const job = data.jobs[Math.min(active, data.jobs.length - 1)]
  const stats = job.stats
  const phases = Object.entries(stats.timings || {}).filter(([k]) => k !== 'total')
  return (
    <div>
      <Failed data={data} />
      <p className="mb-3 text-xs text-muted">
        {data.sample_note} {data.partitions} partitions (reducers) per job.
      </p>

      <div className="mb-4 flex flex-wrap gap-1.5">
        {data.jobs.map((j, i) => (
          <button
            key={j.name}
            type="button"
            onClick={() => setActive(i)}
            className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
              i === active
                ? 'border-accent bg-accent/10 text-accent'
                : 'border-edge text-muted hover:text-zinc-200'
            }`}
          >
            {j.name}
          </button>
        ))}
      </div>

      <p className="mb-1 font-bold">{job.title}</p>
      <p className="text-xs text-muted">
        {job.experiment} · {job.objective}
      </p>

      <div className="my-3 rounded-lg border border-edge/60 bg-base/50 p-3">
        <p className="label">Pipeline</p>
        <ol className="space-y-1 text-xs text-zinc-300">
          {job.pipeline.map((step, i) => (
            <li key={i} className="font-mono">
              {i + 1}. {step}
            </li>
          ))}
        </ol>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Input records" value={stats.input_records.toLocaleString()} />
        <Stat label="Map output pairs" value={stats.map_output_pairs.toLocaleString()} />
        <Stat
          label="Combiner saved"
          value={`${stats.combine_saved_pct}%`}
          sub={`${stats.combine_output_pairs.toLocaleString()} pairs after combine`}
          accent
        />
        <Stat label="Shuffle / reduce groups" value={stats.shuffle_groups.toLocaleString()} />
      </div>

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <div>
          <p className="label">Pairs per partition (reducer)</p>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart
              data={stats.partition_pairs.map((p, i) => ({ name: `R${i}`, pairs: p }))}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2a26" />
              <XAxis dataKey="name" stroke={AXIS} />
              <YAxis stroke={AXIS} />
              <Tooltip contentStyle={CHART_STYLE} />
              <Bar dataKey="pairs" fill="#1ed760" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div>
          <p className="label">Phase timings (seconds)</p>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={phases.map(([name, seconds]) => ({ name, seconds }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2a26" />
              <XAxis dataKey="name" stroke={AXIS} />
              <YAxis stroke={AXIS} />
              <Tooltip contentStyle={CHART_STYLE} />
              <Bar dataKey="seconds" fill="#4f9cf9" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <p className="label">Reduce output ({job.output_columns.join(' · ')})</p>
      <div className="max-h-72 overflow-y-auto rounded-lg border border-edge/60">
        <table className="w-full text-xs">
          <tbody>
            {job.output.map((row, i) => (
              <tr key={i} className="border-b border-edge/30">
                <td className="px-3 py-1.5 font-mono text-accent">{row.key}</td>
                <td className="px-3 py-1.5 font-mono text-zinc-300">{row.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {job.note && <p className="mt-2 text-xs text-muted">{job.note}</p>}
      <ConceptList items={data.concepts} />
    </div>
  )
}

/* ------------------------------------------------------------- Bloom */
function BloomPanel({ data }) {
  if (!data || data.error) return <Failed data={data} />
  const p = data.production
  const lab = data.lab_exercise
  return (
    <div>
      <Failed data={data} />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Items indexed" value={p.n.toLocaleString()} sub={`of ${p.vocabulary_total_distinct.toLocaleString()} distinct`} />
        <Stat label="Bloom size" value={`${p.m.toLocaleString()} bits`} sub={`k = ${p.k} hashes`} />
        <Stat label="Memory" value={`${p.memory_kb} KB`} sub={`vs ~${Math.round(p.bits_vs_naive_kb_saved)} KB of raw strings`} />
        <Stat label="False-positive rate" value={p.theoretical_fpr.toFixed(4)} sub={`empirical ${p.empirical_fpr.toFixed(4)}`} accent />
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Fill ratio" value={`${p.fill_pct}%`} sub={`${p.bits_set.toLocaleString()} bits set`} />
        <Stat label="False negatives" value="0" sub="guaranteed by construction" accent />
        <Stat label="Insert probes verified" value={p.inserted_verified_present} sub="every inserted artist found" />
        <Stat label="Empirical false positives" value={`${p.false_positives} / ${p.probes}`} sub="on never-inserted strings" />
      </div>

      <p className="label">Bit array preview (first {p.bit_preview_len} bits of {p.m.toLocaleString()})</p>
      <pre className="mb-4 max-h-24 overflow-auto rounded-lg border border-edge/60 bg-base/60 p-2 font-mono text-[10px] leading-4 tracking-tight text-accent">
        {p.bit_preview}
      </pre>

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <div>
          <p className="label">Lab exercise · inserts (ASCII → bit positions)</p>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
                <th className="py-2">Word</th>
                <th className="py-2">ASCII sum</th>
                <th className="py-2">Bit positions</th>
              </tr>
            </thead>
            <tbody>
              {lab.inserted.map((r) => (
                <tr key={r.word} className="border-t border-edge/40">
                  <td className="py-1.5 font-mono">{r.word}</td>
                  <td className="py-1.5 text-muted">{r.ascii_sum}</td>
                  <td className="py-1.5 font-mono text-accent">[{r.bit_positions.join(', ')}]</td>
                </tr>
              ))}
            </tbody>
          </table>
          <pre className="mt-2 overflow-x-auto rounded border border-edge/40 bg-base/60 p-2 font-mono text-[11px] text-accent">
            {lab.bit_string}
          </pre>
          <p className="mt-1 text-xs text-muted">
            {lab.bits} bits · {lab.bits_set} set ({lab.fill_pct}% full) · theoretical FPR{' '}
            {lab.theoretical_fpr}
          </p>
        </div>

        <div>
          <p className="label">Lab exercise · membership tests</p>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
                <th className="py-2">Test word</th>
                <th className="py-2">Bits checked</th>
                <th className="py-2">Result</th>
              </tr>
            </thead>
            <tbody>
              {lab.tests.map((r) => (
                <tr key={r.word} className="border-t border-edge/40">
                  <td className="py-1.5 font-mono">{r.word}</td>
                  <td className="py-1.5 font-mono text-muted">
                    [{r.bit_positions.join(', ')}] → [{r.bits.join('')}]
                  </td>
                  <td className="py-1.5">
                    <span
                      className={`badge ${
                        r.status === 'True positive'
                          ? 'border-accent text-accent'
                          : r.status === 'False positive'
                            ? 'border-amber-500 text-amber-300'
                            : 'border-edge text-muted'
                      }`}
                    >
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted">{data.manual_11bit.note}</p>
        </div>
      </div>

      <p className="label">Search pre-filter: skip the scan when the filter says “definitely absent”</p>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
            <th className="py-2">Query</th>
            <th className="py-2">Bloom verdict</th>
            <th className="py-2">Parquet store</th>
          </tr>
        </thead>
        <tbody>
          {data.search_prefilter.queries.map((q) => (
            <tr key={q.query} className="border-t border-edge/40">
              <td className="py-1.5 font-mono">{q.query}</td>
              <td className="py-1.5">{q.bloom_says}</td>
              <td className={`py-1.5 ${q.parquet_scan === 'skipped' ? 'text-accent' : 'text-muted'}`}>
                {q.parquet_scan}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted">
        {data.search_prefilter.scans_avoided} of {data.search_prefilter.queries_total} queries skip
        the store entirely.
      </p>
      <ConceptList items={data.concepts} />
    </div>
  )
}

/* ------------------------------------------------------------- Graph */
function GraphPanel({ data }) {
  const [layout, setLayout] = useState('force')
  if (!data || data.error) return <Failed data={data} />
  const s = data.stats
  const useRing = layout === 'degree_ring'
  return (
    <div>
      <Failed data={data} />
      <p className="mb-3 text-xs text-muted">
        A k-NN cosine graph over {s.nodes} sampled tracks ({s.k_neighbors} neighbours each) stands in
        for the lab's social graph — the corpus has no explicit social edges. Sampled from{' '}
        {s.sampled_from.toLocaleString()} clustered tracks.
      </p>

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Nodes" value={s.nodes} />
        <Stat label="Edges" value={s.edges} sub={`density ${s.density}`} />
        <Stat label="Communities" value={s.communities} sub={`modularity ${s.modularity}`} accent />
        <Stat label="Components" value={s.components} sub={`largest ${s.largest_component}`} />
      </div>
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Avg degree" value={s.avg_degree} />
        <Stat label="Max degree" value={s.max_degree} />
        <Stat label="Avg clustering coeff." value={s.avg_clustering_coefficient} />
        <Stat label="Isolated nodes" value={s.isolated_nodes} />
      </div>

      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="label !mb-0">Layout</span>
        {['force', 'degree_ring'].map((l) => (
          <button
            key={l}
            type="button"
            onClick={() => setLayout(l)}
            className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
              layout === l
                ? 'border-accent bg-accent/10 text-accent'
                : 'border-edge text-muted hover:text-zinc-200'
            }`}
          >
            {l === 'force' ? 'Fruchterman-Reingold' : 'Degree rings'}
          </button>
        ))}
        <span className="text-xs text-muted">node size = degree · colour = community</span>
      </div>

      <div className="mb-4 rounded-lg border border-edge/60 bg-base/60 p-2">
        <svg viewBox="-4 -4 108 108" className="h-[420px] w-full">
          {data.edges.map((e, i) => {
            const a = data.nodes[e.source]
            const b = data.nodes[e.target]
            if (!a || !b) return null
            return (
              <line
                key={i}
                x1={useRing ? a.rx : a.x}
                y1={useRing ? a.ry : a.y}
                x2={useRing ? b.rx : b.x}
                y2={useRing ? b.ry : b.y}
                stroke="#2c3a35"
                strokeWidth="0.25"
              />
            )
          })}
          {data.nodes.map((n) => (
            <circle
              key={n.id + n.name}
              cx={useRing ? n.rx : n.x}
              cy={useRing ? n.ry : n.y}
              r={0.7 + n.degree * 0.09}
              fill={communityColor(n.community)}
              fillOpacity="0.85"
              stroke="#0b0f0e"
              strokeWidth="0.15"
            >
              <title>
                {`${n.name || n.id} — ${n.artists}\ndegree ${n.degree} · community ${n.community} · cluster ${n.cluster}\nPageRank ${n.pagerank}`}
              </title>
            </circle>
          ))}
        </svg>
      </div>

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <div>
          <p className="label">Histogram of node degree</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.degree_histogram}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2a26" />
              <XAxis dataKey="bin" stroke={AXIS} />
              <YAxis stroke={AXIS} />
              <Tooltip contentStyle={CHART_STYLE} />
              <Bar dataKey="count" fill="#1ed760" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div>
          <p className="label">Communities vs acoustic clusters</p>
          <div className="max-h-52 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
                  <th className="py-2">Community</th>
                  <th className="py-2">Size</th>
                  <th className="py-2">Avg degree</th>
                  <th className="py-2">Dominant profile</th>
                </tr>
              </thead>
              <tbody>
                {data.communities.map((c) => (
                  <tr key={c.community} className="border-t border-edge/40">
                    <td className="py-1.5">
                      <span
                        className="badge border-transparent font-bold"
                        style={{
                          background: `${communityColor(c.community)}22`,
                          color: communityColor(c.community),
                        }}
                      >
                        C{c.community}
                      </span>
                    </td>
                    <td className="py-1.5">{c.size}</td>
                    <td className="py-1.5 text-muted">{c.avg_degree}</td>
                    <td className="py-1.5 text-muted">
                      {c.dominant_cluster_label} ({c.dominant_share_pct}%)
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <p className="label">Highest-degree nodes (hubs)</p>
          <ul className="space-y-1 text-xs">
            {data.hubs.map((h) => (
              <li key={h.id + h.name} className="flex justify-between gap-2">
                <span className="truncate">
                  <span className="text-zinc-200">{h.name || h.id}</span>{' '}
                  <span className="text-muted">{h.artists}</span>
                </span>
                <span className="font-mono text-accent">{h.degree}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="label">Top PageRank influence</p>
          <ul className="space-y-1 text-xs">
            {data.influential.map((h) => (
              <li key={`pr-${h.id}${h.name}`} className="flex justify-between gap-2">
                <span className="truncate">
                  <span className="text-zinc-200">{h.name || h.id}</span>{' '}
                  <span className="text-muted">{h.artists}</span>
                </span>
                <span className="font-mono text-accent">{h.pagerank}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <ConceptList items={data.concepts} />
    </div>
  )
}

/* --------------------------------------------------------- Streaming */
function StreamingPanel({ data }) {
  if (!data || data.error) return <Failed data={data} />
  const s = data.stats
  const features = data.features
  const driftByBatch = useMemo(() => {
    const map = {}
    for (const d of data.drift_points) map[d.batch] = d
    return map
  }, [data.drift_points])

  return (
    <div>
      <Failed data={data} />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Events" value={s.events.toLocaleString()} />
        <Stat label="Micro-batches" value={s.batches} sub={`${s.batch_size.toLocaleString()} events each`} />
        <Stat label="Late arrivals" value={`${s.late_pct}%`} sub={`max ${s.max_lateness_years} years behind`} />
        <Stat label="Drift points" value={s.drift_count} sub={`|z| > ${s.drift_z_threshold}`} accent />
      </div>
      <p className="mb-4 text-xs text-muted">{s.note}</p>

      <p className="label">Sliding-window means (window = {s.window} batches)</p>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data.sliding}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2a26" />
          <XAxis dataKey="label" stroke={AXIS} interval="preserveStartEnd" />
          <YAxis stroke={AXIS} domain={[0, 'auto']} />
          <Tooltip contentStyle={CHART_STYLE} />
          <Legend />
          {features.map((f, i) => (
            <Line
              key={f}
              type="monotone"
              dataKey={f}
              stroke={PALETTE[i % PALETTE.length]}
              strokeWidth={2}
              dot={false}
            />
          ))}
          {data.sliding
            .filter((row) => driftByBatch[row.batch])
            .map((row) => (
              <ReferenceLine
                key={`drift-${row.batch}`}
                x={row.label}
                stroke="#ef4444"
                strokeDasharray="3 3"
              />
            ))}
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-1 text-xs text-muted">
        Red dashed lines mark batches where a feature's step deviated from its recent steps — the
        formal version of the decade “vibe shift”.
      </p>

      {data.drift_points.length > 0 && (
        <div className="mt-4">
          <p className="label">Detected change points</p>
          <div className="max-h-64 overflow-y-auto rounded-lg border border-edge/60">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-panel">
                <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
                  <th className="px-3 py-2">Batch</th>
                  <th className="px-3 py-2">Era</th>
                  <th className="px-3 py-2">Feature</th>
                  <th className="px-3 py-2">Step</th>
                  <th className="px-3 py-2">z-score</th>
                </tr>
              </thead>
              <tbody>
                {data.drift_points.map((d, i) => (
                  <tr key={i} className="border-t border-edge/40">
                    <td className="px-3 py-1.5 font-mono">{d.batch}</td>
                    <td className="px-3 py-1.5 text-muted">
                      {d.year_from}s–{d.year_to}s
                    </td>
                    <td className="px-3 py-1.5">{d.feature}</td>
                    <td className="px-3 py-1.5 font-mono text-muted">
                      {d.delta > 0 ? '+' : ''}
                      {d.delta}
                    </td>
                    <td className="px-3 py-1.5 font-mono text-accent">{d.z_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <ConceptList items={data.concepts} />
    </div>
  )
}

/* ---------------------------------------------------------------- ML */
function MlPanel({ data }) {
  if (!data || data.error) return <Failed data={data} />
  const sup = data.supervised || {}
  const elbow = data.elbow || {}
  const hier = data.hierarchical || {}
  const importance = Object.entries(sup.feature_importance || {}).map(([feature, value]) => ({
    feature,
    value,
  }))
  const elbowData = (elbow.k || []).map((k, i) => ({
    k: `k=${k}`,
    inertia: elbow.inertia?.[i],
    silhouette: elbow.silhouette?.[i],
  }))

  return (
    <div>
      <Failed data={data} />
      {sup.error ? (
        <Failed data={sup} />
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat
              label="Target"
              value={<span className="text-base">{sup.target}</span>}
              sub={`${sup.split?.rows_used?.toLocaleString()} rows used`}
            />
            <Stat
              label="Split (70/30)"
              value={`${sup.split?.train_rows?.toLocaleString()} / ${sup.split?.test_rows?.toLocaleString()}`}
              sub={sup.split?.strategy}
            />
            <Stat label="Best model" value={sup.best?.name} sub={`F1 ${sup.best?.f1}`} accent />
            <Stat label="ROC-AUC" value={sup.best?.roc_auc ?? '—'} sub={`accuracy ${sup.best?.accuracy}`} />
          </div>

          <div className="mb-4 grid gap-4 lg:grid-cols-2">
            <div>
              <p className="label">Classifier comparison (held-out test set)</p>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
                    <th className="py-2">Model</th>
                    <th className="py-2">Acc</th>
                    <th className="py-2">Prec</th>
                    <th className="py-2">Rec</th>
                    <th className="py-2">F1</th>
                    <th className="py-2">AUC</th>
                  </tr>
                </thead>
                <tbody>
                  {sup.models.map((m) => (
                    <tr
                      key={m.name}
                      className={`border-t border-edge/40 ${m.name === sup.best?.name ? 'text-accent' : ''}`}
                    >
                      <td className="py-1.5 font-semibold">{m.name}</td>
                      <td className="py-1.5">{m.accuracy}</td>
                      <td className="py-1.5">{m.precision}</td>
                      <td className="py-1.5">{m.recall}</td>
                      <td className="py-1.5">{m.f1}</td>
                      <td className="py-1.5">{m.roc_auc ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-xs text-muted">{sup.distributed_note}</p>
            </div>

            <div>
              <p className="label">Confusion matrix ({sup.best?.name})</p>
              <div className="grid grid-cols-2 gap-2">
                {[
                  ['True negative', sup.confusion_matrix?.[0]?.[0]],
                  ['False positive', sup.confusion_matrix?.[0]?.[1]],
                  ['False negative', sup.confusion_matrix?.[1]?.[0]],
                  ['True positive', sup.confusion_matrix?.[1]?.[1]],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg border border-edge/60 bg-base/60 p-3">
                    <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
                    <p className="stat-value">{value ?? '—'}</p>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted">
                Rows = actual ({sup.confusion_labels?.join(' / ')}), columns = predicted.
              </p>
            </div>
          </div>

          <div className="mb-4 grid gap-4 lg:grid-cols-2">
            <div>
              <p className="label">Feature importance (RandomForest impurity)</p>
              <ResponsiveContainer width="100%" height={230}>
                <BarChart data={importance} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2a26" />
                  <XAxis type="number" stroke={AXIS} />
                  <YAxis type="category" dataKey="feature" stroke={AXIS} width={110} />
                  <Tooltip contentStyle={CHART_STYLE} />
                  <Bar dataKey="value" fill="#1ed760" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div>
              <p className="label">ROC curve ({sup.best?.name})</p>
              <ResponsiveContainer width="100%" height={230}>
                <LineChart data={sup.roc_curve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2a26" />
                  <XAxis dataKey="fpr" stroke={AXIS} domain={[0, 1]} />
                  <YAxis stroke={AXIS} domain={[0, 1]} />
                  <Tooltip contentStyle={CHART_STYLE} />
                  <Line type="monotone" dataKey="tpr" stroke="#4f9cf9" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}

      {elbow.k && (
        <div className="mb-4">
          <p className="label">
            Unsupervised model selection — elbow at k={elbow.elbow_k}, best silhouette at k=
            {elbow.best_silhouette_k}
          </p>
          <div className="grid gap-4 lg:grid-cols-2">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={elbowData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2a26" />
                <XAxis dataKey="k" stroke={AXIS} />
                <YAxis stroke={AXIS} />
                <Tooltip contentStyle={CHART_STYLE} />
                <Line type="monotone" dataKey="inertia" stroke="#1ed760" strokeWidth={2} dot />
              </LineChart>
            </ResponsiveContainer>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={elbowData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2a26" />
                <XAxis dataKey="k" stroke={AXIS} />
                <YAxis stroke={AXIS} />
                <Tooltip contentStyle={CHART_STYLE} />
                <Line type="monotone" dataKey="silhouette" stroke="#f59e0b" strokeWidth={2} dot />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-1 text-xs text-muted">{elbow.note}</p>
        </div>
      )}

      {hier.leaves && <Dendrogram hier={hier} />}
      <ConceptList items={data.concepts} />
    </div>
  )
}

function Dendrogram({ hier }) {
  const maxHeight = hier.max_height || 1
  const maxX = 5 + 10 * Math.max(1, hier.rows_used - 1)
  const labelEvery = Math.max(1, Math.round(hier.rows_used / 14))
  const mapX = (x) => ((x - 5) / (maxX - 5)) * 100
  const mapY = (y) => 30 - (y / maxHeight) * 28
  return (
    <div className="mb-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="label !mb-0">
          Hierarchical clustering dendrogram — {hier.method}, {hier.rows_used} sampled tracks
        </p>
        <span className="text-xs text-muted">ARI vs flat k={hier.clusters_cut}: {hier.ari_vs_agglomerative_cut}</span>
      </div>
      <div className="rounded-lg border border-edge/60 bg-base/60 p-2">
        <svg viewBox="0 0 100 34" className="h-56 w-full">
          {hier.segments.map((s, i) => (
            <line
              key={i}
              x1={mapX(s.x1)}
              y1={mapY(s.y1)}
              x2={mapX(s.x2)}
              y2={mapY(s.y2)}
              stroke="#1ed760"
              strokeWidth="0.18"
              strokeOpacity="0.8"
            />
          ))}
          {hier.leaves.map((leaf, i) => (
            <g key={i}>
              <title>{`${leaf.label} — ${leaf.artists} (${leaf.year}) · cluster ${leaf.cluster}`}</title>
              <circle cx={mapX(leaf.x)} cy={mapY(0)} r="0.35" fill="#8b9a94" />
              {i % labelEvery === 0 && (
                <text
                  x={mapX(leaf.x)}
                  y={33}
                  fontSize="1.6"
                  fill="#8b9a94"
                  textAnchor="end"
                  transform={`rotate(-60 ${mapX(leaf.x)} 33)`}
                >
                  {leaf.label.slice(0, 16)}
                </text>
              )}
            </g>
          ))}
        </svg>
      </div>
      <p className="mt-1 text-xs text-muted">{hier.note}</p>
    </div>
  )
}

/* -------------------------------------------------------------- EDA */
function EdaPanel({ data }) {
  if (!data || data.error) return <Failed data={data} />
  const cols = data.feature_columns
  const corrRows = cols.map((a) => ({ key: a, label: a, cells: data.correlation[a] }))
  const outlierRows = cols.map((c) => ({ feature: c, ...data.outliers[c] }))
  return (
    <div>
      <Failed data={data} />
      <p className="mb-3 rounded-lg border border-edge/60 bg-base/50 px-3 py-2 text-xs text-muted">
        Exp.8 deliverable — the decade × cluster heatmap, cluster-profile heatmap, PCA scatter and
        decade trend lines are rendered above on this page; the panels below add the statistical
        backing (correlation, descriptive statistics, outliers) behind those charts.
      </p>
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Rows analysed" value={data.rows.toLocaleString()} />
        <Stat
          label="Strongest correlation"
          value={data.strongest_pairs?.[0] ? `r = ${data.strongest_pairs[0].r}` : '—'}
          sub={
            data.strongest_pairs?.[0]
              ? `${data.strongest_pairs[0].a} ~ ${data.strongest_pairs[0].b}`
              : undefined
          }
          accent
        />
        <Stat label="IQR outlier flags" value={data.outlier_flags_total.toLocaleString()} />
        <Stat
          label="IsolationForest anomalies"
          value={data.anomaly?.count ?? '—'}
          sub={`${data.anomaly?.pct ?? '—'}% of ${data.anomaly?.sampled?.toLocaleString() ?? '—'} sampled`}
        />
      </div>

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <div>
          <p className="label">Pearson correlation matrix</p>
          <Heatmap
            rowLabel="Feature"
            colLabel="Feature"
            rows={corrRows}
            columns={cols.map((c) => ({ key: c, label: c.slice(0, 6) }))}
            valueFmt={(v) => v.toFixed(2)}
            legend="Amber/green intensity tracks |r|; strong pairs are listed on the right."
          />
        </div>
        <div>
          <p className="label">Strongest relationships</p>
          <table className="w-full text-xs">
            <tbody>
              {data.strongest_pairs.map((p) => (
                <tr key={`${p.a}-${p.b}`} className="border-b border-edge/30">
                  <td className="py-1.5 font-mono">
                    {p.a} ~ {p.b}
                  </td>
                  <td className="py-1.5 text-right font-mono text-accent">{p.r}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 label">Missing values</p>
          <p className="text-xs text-muted">
            {Object.values(data.missing_pct).every((v) => !v)
              ? 'No missing values in the feature matrix after cleaning.'
              : Object.entries(data.missing_pct)
                  .map(([k, v]) => `${k} ${v}%`)
                  .join(' · ')}
          </p>
        </div>
      </div>

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <div>
          <p className="label">IQR outlier counts per feature</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={outlierRows} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2a26" />
              <XAxis type="number" stroke={AXIS} />
              <YAxis type="category" dataKey="feature" stroke={AXIS} width={110} />
              <Tooltip contentStyle={CHART_STYLE} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {outlierRows.map((_, i) => (
                  <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div>
          <p className="label">Descriptive statistics</p>
          <div className="max-h-56 overflow-y-auto rounded-lg border border-edge/60">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-panel">
                <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
                  <th className="px-2 py-2">Feature</th>
                  <th className="px-2 py-2">Mean</th>
                  <th className="px-2 py-2">Std</th>
                  <th className="px-2 py-2">Min</th>
                  <th className="px-2 py-2">Med</th>
                  <th className="px-2 py-2">Max</th>
                  <th className="px-2 py-2">Skew</th>
                </tr>
              </thead>
              <tbody>
                {cols.map((c) => (
                  <tr key={c} className="border-t border-edge/40">
                    <td className="px-2 py-1.5 font-mono">{c}</td>
                    <td className="px-2 py-1.5">{data.stats[c]?.mean}</td>
                    <td className="px-2 py-1.5">{data.stats[c]?.std}</td>
                    <td className="px-2 py-1.5">{data.stats[c]?.min}</td>
                    <td className="px-2 py-1.5">{data.stats[c]?.median}</td>
                    <td className="px-2 py-1.5">{data.stats[c]?.max}</td>
                    <td className="px-2 py-1.5 text-muted">{data.stats[c]?.skew}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <ConceptList items={data.concepts} />
    </div>
  )
}

/* ------------------------------------------------------------ NoSQL */
function NosqlPanel({ data }) {
  if (!data || data.error) return <Failed data={data} />
  const s = data.stats || {}
  return (
    <div>
      <Failed data={data} />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label="Backend"
          value={<span className="text-base">{data.backend}</span>}
          sub={`${data.database}.${data.collection}`}
        />
        <Stat label="Documents" value={(s.documents ?? 0).toLocaleString()} />
        <Stat
          label="Avg document size"
          value={s.avg_obj_size ? `${Math.round(s.avg_obj_size)} B` : '—'}
          sub={s.storage_bytes ? `${Math.round(s.storage_bytes / 1024)} KB on disk` : undefined}
        />
        <Stat
          label="Runs by state"
          value={(s.done ?? 0).toLocaleString()}
          sub={`done · ${s.running ?? 0} running · ${s.failed ?? 0} failed`}
        />
      </div>
      <p className="mb-4 text-xs text-muted">{s.note}</p>

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <div>
          <p className="label">Queries executed against the live collection</p>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
                <th className="py-2">Filter / pipeline</th>
                <th className="py-2">Result</th>
              </tr>
            </thead>
            <tbody>
              {(data.queries || []).map((q, i) => (
                <tr key={i} className="border-t border-edge/40">
                  <td className="py-1.5 font-mono text-[11px]" title={q.desc}>
                    {q.filter}
                  </td>
                  <td className="py-1.5 text-accent">{q.result}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <p className="label">Document schema paths (schemaless)</p>
          <div className="max-h-56 overflow-y-auto rounded-lg border border-edge/60">
            <table className="w-full text-xs">
              <tbody>
                {(data.schema || []).map((row) => (
                  <tr key={row.path} className="border-b border-edge/30">
                    <td className="px-2 py-1 font-mono text-[11px]">{row.path}</td>
                    <td className="px-2 py-1 text-muted">{row.type}</td>
                    <td className="max-w-[180px] truncate px-2 py-1 text-muted" title={row.sample}>
                      {row.sample}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <p className="label">Command transcript ({data.commands.length} commands — read-only)</p>
      <div className="max-h-72 overflow-y-auto rounded-lg border border-edge/60">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-panel">
            <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
              <th className="px-3 py-2">#</th>
              <th className="px-3 py-2">Command</th>
              <th className="px-3 py-2">Purpose</th>
              <th className="px-3 py-2">Result</th>
            </tr>
          </thead>
          <tbody>
            {data.commands.map((c, i) => (
              <tr key={i} className="border-t border-edge/40">
                <td className="px-3 py-1.5 text-muted">{i + 1}</td>
                <td className="max-w-[280px] truncate px-3 py-1.5 font-mono text-[11px] text-accent" title={c.cmd}>
                  {c.cmd}
                </td>
                <td className="px-3 py-1.5 text-muted">{c.purpose}</td>
                <td className="max-w-[200px] truncate px-3 py-1.5" title={c.result}>
                  {c.result}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.sample_document && (
        <div className="mt-4">
          <p className="label">Sample run document</p>
          <pre className="max-h-64 overflow-auto rounded-lg border border-edge/60 bg-base/60 p-3 font-mono text-[11px] text-zinc-300">
            {data.sample_document}
          </pre>
        </div>
      )}
      <ConceptList items={data.concepts} />
    </div>
  )
}
