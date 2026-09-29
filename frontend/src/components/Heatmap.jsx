const PALETTE = ['#0e1512', '#123527', '#175738', '#1d7a4b', '#24a05e', '#2ecc71', '#7dedb0']

function colorFor(t) {
  const i = Math.min(PALETTE.length - 1, Math.max(0, Math.floor(t * (PALETTE.length - 1) + 0.5)))
  return PALETTE[i]
}

export default function Heatmap({
  rowLabel,
  colLabel,
  rows, // [{ key, label, cells: {colKey: value}, max }]
  columns, // [{ key, label }]
  valueFmt = (v) => v.toFixed(1),
  legend,
}) {
  const max = Math.max(
    1e-9,
    ...rows.flatMap((r) => columns.map((c) => Number(r.cells[c.key]) || 0)),
  )
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-1 text-xs">
        <thead>
          <tr>
            <th className="w-24 text-left font-semibold uppercase tracking-wider text-muted">{rowLabel}</th>
            {columns.map((c) => (
              <th key={c.key} className="px-1 pb-1 text-center font-semibold text-muted">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <td className="pr-2 text-right font-semibold text-zinc-200">{r.label}</td>
              {columns.map((c) => {
                const v = Number(r.cells[c.key]) || 0
                const t = v / max
                return (
                  <td
                    key={c.key}
                    className="rounded-md py-2 text-center font-mono font-semibold"
                    style={{ background: colorFor(t), color: t > 0.55 ? '#052012' : '#cfe9db' }}
                    title={`${r.label} × ${c.label}: ${valueFmt(v)}`}
                  >
                    {valueFmt(v)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {legend && <p className="mt-2 text-xs text-muted">{legend}</p>}
    </div>
  )
}
