import { supabase } from '@/lib/supabase'

export async function apiFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  const session = supabase ? (await supabase.auth.getSession()).data.session : null
  const devUser = localStorage.getItem('yeseee_dev_user_id')
  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`)
  } else if (devUser) {
    headers.set('Authorization', `Bearer ${devUser}`)
    headers.set('X-Dev-User-Id', devUser)
  }
  const res = await fetch(path, { ...init, headers })
  if (!res.ok) {
    const t = await res.text()
    throw new Error(t || res.statusText)
  }
  if (res.status === 204) return null
  const ct = res.headers.get('content-type')
  if (ct?.includes('application/json')) return res.json()
  return res.text()
}
