import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { supabase } from '@/lib/supabase'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { apiFetch } from '@/api/client'

export function AuthPage() {
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [devId, setDevId] = useState('')
  const [msg, setMsg] = useState('')

  const syncUser = async (userId: string, userEmail?: string) => {
    localStorage.setItem('yeseee_dev_user_id', userId)
    await apiFetch('/api/auth/sync', { method: 'POST', body: JSON.stringify({ email: userEmail ?? null }) })
  }

  const onDev = async () => {
    try {
      const id = devId.trim() || crypto.randomUUID()
      await syncUser(id, `dev-${id.slice(0, 8)}@local.test`)
      nav('/onboard')
    } catch (e) {
      setMsg(String(e))
    }
  }

  const onGoogle = async () => {
    if (!supabase) {
      setMsg('Configure VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY')
      return
    }
    await supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin } })
  }

  const onEmail = async () => {
    if (!supabase || !email) return
    await supabase.auth.signInWithOtp({ email, options: { emailRedirectTo: window.location.origin } })
    setMsg('Check your email for the magic link.')
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md">
        <Card className="border-zinc-800">
          <CardHeader>
            <CardTitle className="text-2xl">yeseeeooo</CardTitle>
            <CardDescription>AI-native SEO & GEO — sign in to spin up your agent team.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {supabase ? (
              <>
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" type="email" />
                  <Button variant="secondary" className="w-full" onClick={onEmail}>
                    Email magic link
                  </Button>
                </div>
                <Button variant="outline" className="w-full" onClick={onGoogle}>
                  Continue with Google
                </Button>
              </>
            ) : (
              <p className="text-sm text-amber-200/90">Supabase env not set — use local dev user below.</p>
            )}
            <div className="space-y-2 border-t border-zinc-800 pt-4">
              <Label>Local dev user UUID (optional)</Label>
              <Input value={devId} onChange={(e) => setDevId(e.target.value)} placeholder="Leave empty to auto-generate" />
              <Button className="w-full" onClick={onDev}>
                Continue in dev mode
              </Button>
            </div>
            {msg ? <p className="text-sm text-zinc-400">{msg}</p> : null}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}
