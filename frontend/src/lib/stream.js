import { API_BASE, refreshTokens } from './api'
import { useAuth } from '../store/auth'

/**
 * POST /chat/ask and consume the text/event-stream response.
 * Uses fetch (not axios/EventSource) because we need POST + auth headers
 * and incremental reads of the response body.
 */
export async function streamQuestion(question, { onEvent, signal }) {
  let res = await send(question, signal)
  if (res.status === 401 && useAuth.getState().refreshToken) {
    await refreshTokens()
    res = await send(question, signal)
  }
  if (!res.ok) {
    let detail = 'Request failed'
    try {
      detail = (await res.json()).detail || detail
    } catch {
      /* not JSON */
    }
    const err = new Error(detail)
    err.status = res.status
    throw err
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      const line = block.split('\n').find((l) => l.startsWith('data: '))
      if (line) onEvent(JSON.parse(line.slice(6)))
    }
  }
}

function send(question, signal) {
  return fetch(`${API_BASE}/chat/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${useAuth.getState().accessToken}`,
    },
    body: JSON.stringify({ question }),
    signal,
  })
}
