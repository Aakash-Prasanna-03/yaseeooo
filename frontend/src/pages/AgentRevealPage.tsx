import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AGENTS } from '@/data/agents'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useWorkspaceStore } from '@/store/workspaceStore'

export function AgentRevealPage() {
  const nav = useNavigate()
  const { brandColors } = useWorkspaceStore()

  return (
    <div className="min-h-screen px-4 py-10 md:px-10">
      <div className="mx-auto max-w-5xl">
        <p className="text-center text-xs font-medium uppercase tracking-widest text-violet-400">Agent team reveal</p>
        <h1 className="mt-2 text-center text-3xl font-bold text-white md:text-4xl">Your squad is assembled</h1>
        <p className="mx-auto mt-2 max-w-2xl text-center text-zinc-400">
          Seven specialists, one brand memory. Each card previews their first move once you activate.
        </p>

        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {AGENTS.map((a, i) => (
            <motion.div
              key={a.name}
              initial={{ opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.07, type: 'spring', stiffness: 120, damping: 18 }}
            >
              <Card
                className="h-full overflow-hidden border-zinc-800"
                style={{
                  borderColor: `${brandColors.primary}55`,
                  boxShadow: `0 0 0 1px ${brandColors.primary}22`,
                }}
              >
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full" style={{ backgroundColor: a.color }} />
                    <div>
                      <CardTitle className="text-base">{a.name}</CardTitle>
                      <CardDescription>{a.role}</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-zinc-300">
                  <p className="text-xs text-violet-300/90">{a.platforms}</p>
                  <p>{a.tagline}</p>
                  <p className="rounded-md bg-zinc-950/80 p-2 text-xs text-zinc-500">
                    First action: calibrate {a.name === 'Nova' ? 'weekly score & GEO signals' : 'draft outline aligned to your keywords'}.
                  </p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        <div className="mt-10 flex justify-center">
          <Button
            size="lg"
            className="min-w-[220px]"
            style={{ backgroundColor: brandColors.primary }}
            onClick={() => nav('/dashboard')}
          >
            Activate my team
          </Button>
        </div>
      </div>
    </div>
  )
}
