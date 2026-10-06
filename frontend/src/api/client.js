const BASE = '/api'

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      /* keep statusText */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  datasetStatus: (refresh = false) =>
    fetch(`${BASE}/dataset/status${refresh ? '?refresh=true' : ''}`).then(handle),
  engineStatus: () => fetch(`${BASE}/engine`).then(handle),
  storeInfo: () => fetch(`${BASE}/store`).then(handle),
  concepts: (runId) =>
    fetch(`${BASE}/concepts${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`).then(handle),
  createRun: (config) =>
    fetch(`${BASE}/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }).then(handle),
  listRuns: (limit = 25) => fetch(`${BASE}/runs?limit=${limit}`).then(handle),
  runStatus: (id) => fetch(`${BASE}/runs/${id}`).then(handle),
  runResults: (id) => fetch(`${BASE}/runs/${id}/results`).then(handle),
  runTracks: (id, params) => {
    const qs = new URLSearchParams()
    if (params.search) qs.set('search', params.search)
    if (params.cluster !== undefined && params.cluster !== null && params.cluster !== '')
      qs.set('cluster', params.cluster)
    if (params.decade !== undefined && params.decade !== null && params.decade !== '')
      qs.set('decade', params.decade)
    qs.set('page', params.page || 1)
    qs.set('page_size', params.pageSize || 50)
    return fetch(`${BASE}/runs/${id}/tracks?${qs}`).then(handle)
  },
  bloomCheck: (id, term) =>
    fetch(`${BASE}/runs/${id}/bloom?term=${encodeURIComponent(term || '')}`).then(handle),
  notebookUrl: (id) => `${BASE}/runs/${id}/notebook`,
}
