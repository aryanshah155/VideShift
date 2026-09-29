import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client.js'

/**
 * Polls run status every 1.5s while the run is queued/running.
 * Returns { status, error, refresh }.
 */
export function useRunPoll(runId) {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const timer = useRef(null)

  const refresh = () =>
    api
      .runStatus(runId)
      .then(setStatus)
      .catch((e) => setError(e.message))

  useEffect(() => {
    if (!runId) return undefined
    refresh()
    timer.current = setInterval(refresh, 1500)
    return () => clearInterval(timer.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId])

  const state = status?.state
  useEffect(() => {
    if (state === 'done' || state === 'failed') clearInterval(timer.current)
  }, [state])

  return { status, error, refresh }
}
