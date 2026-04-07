import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { apiFetch } from '@/api/client'
import { Button } from '@/components/ui/button'

export function CrawlWaitPage() {
  const nav = useNavigate()
  const { workspaceId, setBrandColors } = useWorkspaceStore()
  const [tick, setTick] = useState(0)
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!workspaceId) {
      nav('/onboard')
      return
    }
    const t = setInterval(() => setTick((x) => x + 1), 2000)
    return () => clearInterval(t)
  }, [workspaceId, nav])

  useEffect(() => {
    if (!workspaceId) return
    ;(async () => {
      try {
        const res = (await apiFetch(`/api/brand-profile/${workspaceId}`)) as {
          profile: { crawled_at?: string; colors?: Record<string, string> } | null
        }
        if (res.profile?.crawled_at) {
          const c = res.profile.colors || {}
          setBrandColors({
            primary: (c.primary as string) || undefined,
            secondary: (c.secondary as string) || undefined,
            accent: (c.accent as string) || undefined,
          })
          setDone(true)
        }
      } catch {
        /* network */
      }
    })()
  }, [workspaceId, tick, setBrandColors])

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 p-6 text-center">
      <motion.div
        animate={{ scale: [1, 1.04, 1] }}
        transition={{ repeat: Infinity, duration: 2.4 }}
        className="h-24 w-24 rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-600 opacity-90 blur-0"
      />
      <div>
        <h1 className="text-2xl font-semibold text-white">Your team is getting to know you…</h1>
        <p className="mt-2 max-w-md text-sm text-zinc-400">
          We extract colors, tone, keywords, competitors, social handles, CTAs, and content structure — usually under a minute.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-3">
        {done ? (
          <Button onClick={() => nav('/reveal')}>Meet my agents</Button>
        ) : (
          <Button variant="secondary" onClick={() => nav('/reveal')}>
            Skip wait (demo)
          </Button>
        )}
        <Button variant="outline" onClick={() => nav('/brand')}>
          View brand report
        </Button>
      </div>
    </div>
  )
}
