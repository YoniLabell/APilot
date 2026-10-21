import type {Answer, TEvent} from '../types'

/** The server has no streaming endpoint (or a proxy strips it): fall back to the plain request. */
export class StreamUnavailable extends Error {}

function errorDetail(result: unknown, status: number) {
  const detail = (result as {detail?: unknown})?.detail
  return typeof detail === 'string' ? detail : `Request failed (${status})`
}

export async function api<T = unknown>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(url, options)
  const result = await resp.json().catch(() => ({}))
  if (!resp.ok) throw Error(errorDetail(result, resp.status))
  return result as T
}

type AskBody = {question: string; forced_api: string}

function headers(key: string) {
  return {'Content-Type': 'application/json', 'X-APilot-Key': key}
}

export function ask(body: AskBody, key: string, signal: AbortSignal) {
  return api<Answer>('/api/ask', {method: 'POST', headers: headers(key), body: JSON.stringify(body), signal})
}

/** POSTs the question and reads Server-Sent Events: `trace` events while working, then `result` or `error`. */
export async function askStream(body: AskBody, key: string, onTrace: (event: TEvent) => void, signal: AbortSignal): Promise<Answer> {
  const resp = await fetch('/api/ask/stream', {
    method: 'POST', headers: {...headers(key), Accept: 'text/event-stream'}, body: JSON.stringify(body), signal,
  })
  if (resp.status === 404 || resp.status === 405) throw new StreamUnavailable()
  if (!resp.ok) throw Error(errorDetail(await resp.json().catch(() => ({})), resp.status))
  if (!resp.body || !resp.headers.get('content-type')?.includes('text/event-stream')) throw new StreamUnavailable()

  const reader = resp.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const {value, done} = await reader.read()
    if (done) break
    buffer += value.replace(/\r\n/g, '\n')
    let end: number
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const chunk = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      let event = 'message'
      let data = ''
      for (const line of chunk.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (!data) continue
      const payload = JSON.parse(data)
      if (event === 'trace') onTrace(payload as TEvent)
      else if (event === 'result') return payload as Answer
      else if (event === 'error') throw Error(errorDetail(payload, 422))
    }
  }
  throw Error('The connection closed before the agent finished. Please try again.')
}
