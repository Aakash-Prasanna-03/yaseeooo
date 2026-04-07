import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { Checkbox } from '@/components/ui/checkbox'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { apiFetch } from '@/api/client'

const PLATFORMS = ['Reddit', 'LinkedIn', 'Medium', 'Quora', 'WordPress'] as const

const QUESTIONS = [
  { key: 'businessName' as const, title: "What's your business called?", subtitle: 'This anchors every agent brief.', type: 'text' },
  { key: 'businessDescription' as const, title: 'What does your business do?', subtitle: '2–3 sentences. We seed your voice from this.', type: 'area' },
  { key: 'websiteUrl' as const, title: "What's your website?", subtitle: 'We crawl it in under 60 seconds once you finish the journey.', type: 'url' },
  { key: 'competitors' as const, title: 'Who competes with you?', subtitle: 'Optional — comma-separated names or URLs.', type: 'text' },
  { key: 'targetAudience' as const, title: 'Who are you trying to reach?', subtitle: 'Guides tone and channel mix.', type: 'area' },
  { key: 'platforms' as const, title: 'Which platforms matter most?', subtitle: 'Select all that apply.', type: 'platforms' },
  { key: 'primaryGoal' as const, title: 'Primary goal for the next 90 days?', subtitle: 'We weight the agent plan accordingly.', type: 'goal' },
]

export function OnboardPage() {
  const nav = useNavigate()
  const { onboarding, setOnboarding, setWorkspaceId } = useWorkspaceStore()
  const [step, setStep] = useState(0)
  const [err, setErr] = useState('')
  const pct = ((step + 1) / 7) * 100

  const q = QUESTIONS[step]

  const next = () => {
    setErr('')
    if (step < 6) setStep((s) => s + 1)
    else submit()
  }

  const back = () => setStep((s) => Math.max(0, s - 1))

  const togglePlatform = (p: string) => {
    const set = new Set(onboarding.platforms)
    if (set.has(p)) set.delete(p)
    else set.add(p)
    setOnboarding({ platforms: [...set] })
  }

  const submit = async () => {
    try {
      const competitors = onboarding.competitors
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
      const body = {
        business_name: onboarding.businessName,
        business_description: onboarding.businessDescription,
        website_url: onboarding.websiteUrl,
        competitors,
        target_audience: onboarding.targetAudience,
        platforms: onboarding.platforms.map((p) => p.toLowerCase()),
        primary_goal: onboarding.primaryGoal,
      }
      const res = (await apiFetch('/api/onboard', { method: 'POST', body: JSON.stringify(body) })) as { workspace_id: string }
      setWorkspaceId(res.workspace_id)
      nav('/crawl')
    } catch (e) {
      setErr(String(e))
    }
  }

  const valueForInput = () => {
    if (q.key === 'platforms' || q.key === 'primaryGoal') return ''
    return onboarding[q.key] as string
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-6 p-6">
      <div>
        <p className="text-xs font-medium uppercase tracking-widest text-violet-400">Onboarding</p>
        <h1 className="mt-1 text-2xl font-semibold text-white">Step {step + 1} of 7</h1>
        <Progress value={pct} className="mt-3" />
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -24 }}
          transition={{ duration: 0.22 }}
          className="space-y-4"
        >
          <h2 className="text-xl font-medium text-zinc-100">{q.title}</h2>
          <p className="text-sm text-zinc-400">{q.subtitle}</p>

          {q.type === 'text' || q.type === 'url' ? (
            <Input
              value={valueForInput()}
              onChange={(e) => setOnboarding({ [q.key]: e.target.value })}
              placeholder={q.type === 'url' ? 'https://' : ''}
            />
          ) : null}

          {q.type === 'area' ? (
            <textarea
              className="min-h-[120px] w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
              value={valueForInput()}
              onChange={(e) => setOnboarding({ [q.key]: e.target.value })}
            />
          ) : null}

          {q.type === 'platforms' ? (
            <div className="flex flex-col gap-3">
              {PLATFORMS.map((p) => (
                <label key={p} className="flex items-center gap-2 text-sm text-zinc-200">
                  <Checkbox checked={onboarding.platforms.includes(p)} onCheckedChange={() => togglePlatform(p)} />
                  {p}
                </label>
              ))}
            </div>
          ) : null}

          {q.type === 'goal' ? (
            <div className="flex flex-col gap-2">
              {(
                [
                  ['traffic', 'Organic traffic & rankings'],
                  ['brand_awareness', 'Brand awareness & share of voice'],
                  ['lead_generation', 'Lead generation & pipeline'],
                ] as const
              ).map(([k, label]) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => setOnboarding({ primaryGoal: k })}
                  className={`rounded-lg border px-4 py-3 text-left text-sm transition-colors ${
                    onboarding.primaryGoal === k
                      ? 'border-violet-500 bg-violet-950/40 text-white'
                      : 'border-zinc-700 bg-zinc-950 text-zinc-300 hover:border-zinc-600'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          ) : null}
        </motion.div>
      </AnimatePresence>

      {err ? <p className="text-sm text-red-400">{err}</p> : null}

      <div className="flex gap-3">
        <Button variant="secondary" type="button" onClick={back} disabled={step === 0}>
          Back
        </Button>
        <Button
          className="flex-1"
          type="button"
          onClick={next}
          disabled={
            (q.key === 'platforms' && onboarding.platforms.length === 0) ||
            (q.key === 'primaryGoal' && !onboarding.primaryGoal) ||
            (q.type !== 'platforms' &&
              q.type !== 'goal' &&
              !(onboarding[q.key as keyof typeof onboarding] as string)?.trim())
          }
        >
          {step === 6 ? 'Launch my team' : 'Continue'}
        </Button>
      </div>
    </div>
  )
}
