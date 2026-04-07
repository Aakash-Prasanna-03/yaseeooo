import { useEffect, useRef, useState } from 'react'
import { supabase } from '@/lib/supabase'

export type SseEvent = Record<string, unknown>

function parseSseChunk(buffer: string): { events: SseEvent[]; rest: string } {
  const events: SseEvent[] = []
  const parts = buffer.split('\n\n')
  const rest = parts.pop() ?? ''
  for (const block of parts) {
    for (const line of block.split('\n')) {
      if (line.startsWith('data:')) {
        const raw = line.slice(5).trim()
        if (raw && raw !== '[DONE]') {
          try {
            events.push(JSON.parse(raw) as SseEvent)
          } catch {
            /* keepalive */
          }
        }
      }
    }
  }
  return { events, rest }
}

export function useAgentSse(workspaceId: string | null, enabled: boolean) {
  const [events, setEvents] = useState<SseEvent[]>([])
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!workspaceId || !enabled) return
    const ac = new AbortController()
    abortRef.current = ac
    let buf = ''

    ;(async () => {
      const headers: Record<string, string> = {}
      const session = supabase ? (await supabase.auth.getSession()).data.session : null
      const dev = localStorage.getItem('yeseee_dev_user_id')
      if (session?.access_token) headers.Authorization = `Bearer ${session.access_token}`
      else if (dev) {
        headers.Authorization = `Bearer ${dev}`
        headers['X-Dev-User-Id'] = dev
      }
      const res = await fetch(`/api/agents/stream/${workspaceId}`, { headers, signal: ac.signal })
      const reader = res.body?.getReader()
      if (!reader) return
      const dec = new TextDecoder()
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const { events: evs, rest } = parseSseChunk(buf)
        buf = rest
        if (evs.length) setEvents((prev) => [...evs, ...prev].slice(0, 200))
      }
    })().catch(() => {})

    return () => ac.abort()
  }, [workspaceId, enabled])

  return events
}
