export default function Stat({ label, value, sub, accent, title }) {
  return (
    <div className="card !p-4" title={title}>
      <p className="text-xs font-semibold uppercase tracking-wider text-muted">{label}</p>
      <p className={`stat-value mt-1 ${accent ? 'text-accent' : ''}`}>{value}</p>
      {sub && <p className="text-xs text-muted">{sub}</p>}
    </div>
  )
}
