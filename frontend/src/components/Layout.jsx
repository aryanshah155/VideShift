import { Link, useLocation } from 'react-router-dom'

export default function Layout({ children }) {
  const { pathname } = useLocation()
  const onResults = pathname.startsWith('/runs/')
  const runId = onResults ? pathname.split('/')[2] : null
  const pill = (active) =>
    `rounded-full px-4 py-1.5 transition ${active ? 'bg-panel text-accent border border-edge' : 'text-muted hover:text-zinc-100'}`
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-edge bg-base/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-accent text-base">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M9 18V5l12-2v13" stroke="currentColor" strokeWidth="2" fill="none" />
                <circle cx="6" cy="18" r="3" />
                <circle cx="18" cy="16" r="3" />
              </svg>
            </span>
            <span className="text-lg font-extrabold tracking-tight">
              Vibe<span className="text-accent">Shift</span>
            </span>
          </Link>
          <nav className="flex items-center gap-2 text-sm font-semibold">
            <Link to="/" className={pill(pathname === '/')}>
              Dashboard
            </Link>
            <Link to="/concepts" className={pill(pathname.startsWith('/concepts'))}>
              Concepts
            </Link>
            {onResults && (
              <>
                <Link to={`/runs/${runId}`} className={pill(pathname.endsWith(runId))}>
                  Results
                </Link>
                <Link
                  to={`/runs/${runId}/tracks`}
                  className={pill(pathname.endsWith('/tracks'))}
                >
                  Tracks
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
    </div>
  )
}
