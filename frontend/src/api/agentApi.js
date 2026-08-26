async function request(path, options = {}) {
  const response = await fetch(`/api/agent${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body?.detail
    const message = typeof detail === 'string'
      ? detail
      : detail?.message || body?.message || `请求失败（${response.status}）`
    const error = new Error(message)
    error.status = response.status
    error.detail = detail
    throw error
  }
  return body
}

export const agentApi = {
  createRun(payload) {
    return request('/runs', { method: 'POST', body: JSON.stringify(payload) })
  },
  getRun(runId) {
    return request(`/runs/${encodeURIComponent(runId)}`)
  },
  listRuns(sessionId, limit = 20) {
    const query = new URLSearchParams({ session_id: String(sessionId), limit: String(limit) })
    return request(`/runs?${query}`)
  },
  cancelRun(runId) {
    return request(`/runs/${encodeURIComponent(runId)}/cancel`, { method: 'POST' })
  },
  retryRun(runId) {
    return request(`/runs/${encodeURIComponent(runId)}/retry`, { method: 'POST' })
  },
  listModels() {
    return request('/models')
  },
  listSkills() {
    return request('/skills')
  },
}
