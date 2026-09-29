const ICONS = {
  pending: '○',
  running: '◔',
  done: '●',
  failed: '✕',
}

const COLORS = {
  pending: 'text-muted',
  running: 'text-accent animate-pulse',
  done: 'text-accent',
  failed: 'text-red-400',
}

export default function StageConsole({ stages }) {
  if (!stages) return null
  return (
    <ol className="space-y-2 font-mono text-sm">
      {stages.map((s) => (
        <li key={s.name} className="flex items-center gap-3">
          <span className={`${COLORS[s.status]} w-4 text-center`}>{ICONS[s.status]}</span>
          <span className={`w-24 font-semibold ${s.status === 'pending' ? 'text-muted' : 'text-zinc-100'}`}>
            {s.name}
          </span>
          <span className="flex-1 truncate text-muted">{s.detail || '—'}</span>
          {s.seconds != null && <span className="tabular-nums text-zinc-400">{s.seconds.toFixed(2)}s</span>}
        </li>
      ))}
    </ol>
  )
}
