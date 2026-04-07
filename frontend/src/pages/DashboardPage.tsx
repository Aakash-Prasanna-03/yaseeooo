import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { AGENTS } from '@/data/agents'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { useAgentSse } from '@/hooks/useAgentSse'
import { apiFetch } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Separator } from '@/components/ui/separator'

export function DashboardPage() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const { workspaceId, brandColors } = useWorkspaceStore()
  const [agentFilter, setAgentFilter] = useState<string | null>(null)
  const [expandedDraftId, setExpandedDraftId] = useState<string | null>(null)
  const [range, setRange] = useState<'7d' | '30d' | '90d'>('30d')
  const [geoEngine, setGeoEngine] = useState<string | 'all'>('all')

  const sse = useAgentSse(workspaceId, true)

  const { data: analytics } = useQuery({
    queryKey: ['analytics', workspaceId],
    enabled: !!workspaceId,
    queryFn: () => apiFetch(`/api/analytics/${workspaceId}`) as Promise<Record<string, unknown>>,
  })

  const { data: keywordsData } = useQuery({
    queryKey: ['keywords', workspaceId],
    enabled: !!workspaceId,
    queryFn: () => apiFetch(`/api/keywords/${workspaceId}`) as Promise<{ items: Record<string, unknown>[] }>,
  })

  const { data: backlinksData } = useQuery({
    queryKey: ['backlinks', workspaceId],
    enabled: !!workspaceId,
    queryFn: () => apiFetch(`/api/backlinks/${workspaceId}`) as Promise<{ items: Record<string, unknown>[]; total: number }>,
  })

  const { data: geoData } = useQuery({
    queryKey: ['geo', workspaceId],
    enabled: !!workspaceId,
    queryFn: () => apiFetch(`/api/geo/${workspaceId}`) as Promise<{ items: Record<string, unknown>[] }>,
  })

  const { data: draftsData } = useQuery({
    queryKey: ['drafts', workspaceId],
    enabled: !!workspaceId,
    queryFn: () =>
      apiFetch(`/api/content/${workspaceId}`) as Promise<{ items: Record<string, unknown>[] }>,
    refetchInterval: 8000,
  })

  const { data: activityData } = useQuery({
    queryKey: ['activity', workspaceId],
    enabled: !!workspaceId,
    queryFn: () => apiFetch(`/api/activity/${workspaceId}?page_size=50`) as Promise<{ items: Record<string, unknown>[] }>,
    refetchInterval: 15000,
  })

  const { data: compData } = useQuery({
    queryKey: ['competitors', workspaceId],
    enabled: !!workspaceId,
    queryFn: () => apiFetch(`/api/competitors/${workspaceId}`) as Promise<{ items: Record<string, unknown>[] }>,
  })

  const { data: wsStatus } = useQuery({
    queryKey: ['workspace-status', workspaceId],
    enabled: !!workspaceId,
    queryFn: () =>
      apiFetch(`/api/workspace/${workspaceId}/status`) as Promise<{
        crawl_completed: boolean
        pending_plan_items: number
      }>,
    refetchInterval: 6000,
  })

  const approve = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/content/${id}/approve`, { method: 'PATCH' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['drafts', workspaceId] }),
  })

  const reject = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/content/${id}/reject`, { method: 'PATCH' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['drafts', workspaceId] }),
  })

  const triggerCycle = useMutation({
    mutationFn: () =>
      apiFetch('/api/content-cycle/trigger', {
        method: 'POST',
        body: JSON.stringify({ workspace_id: workspaceId }),
      }),
  })

  const runAgent = useMutation({
    mutationFn: (agent: string) =>
      apiFetch('/api/agents/run', {
        method: 'POST',
        body: JSON.stringify({ workspace_id: workspaceId, agent }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['drafts', workspaceId] })
      qc.invalidateQueries({ queryKey: ['workspace-status', workspaceId] })
      qc.invalidateQueries({ queryKey: ['activity', workspaceId] })
    },
  })

  const queueCrawl = useMutation({
    mutationFn: () =>
      apiFetch(`/api/crawl?workspace_id=${encodeURIComponent(workspaceId!)}`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workspace-status', workspaceId] }),
  })

  const chartData = useMemo(() => {
    const items = keywordsData?.items ?? []
    const byKw: Record<string, { t: string; rank: number }[]> = {}
    for (const row of items) {
      const kw = String(row.keyword)
      const t = new Date(String(row.checked_at)).toISOString().slice(0, 10)
      const pos = Number(row.position ?? 0)
      if (!byKw[kw]) byKw[kw] = []
      byKw[kw].push({ t, rank: pos })
    }
    const dates = [...new Set(items.map((r) => new Date(String(r.checked_at)).toISOString().slice(0, 10)))].sort()
    return dates.map((d) => {
      const point: Record<string, string | number> = { date: d }
      for (const kw of Object.keys(byKw)) {
        const hit = byKw[kw].find((x) => x.t === d)
        if (hit) point[kw] = hit.rank
      }
      return point
    })
  }, [keywordsData])

  const approvalDrafts = (draftsData?.items ?? []).filter(
    (d) => d.status === 'awaiting_approval' || d.status === 'pending',
  )
  const isQuotaFallbackDraft = (d: Record<string, unknown>) =>
    String(d.body ?? '').trimStart().startsWith('[quota-fallback]')

  const filteredSse = agentFilter ? sse.filter((e) => String(e.agent) === agentFilter) : sse

  const exportCsv = () => {
    const rows = draftsData?.items ?? []
    const header = ['id', 'agent', 'type', 'platform', 'status', 'preview']
    const lines = [
      header.join(','),
      ...rows.map((r) =>
        [
          r.id,
          r.agent_name,
          r.content_type,
          r.platform,
          r.status,
          JSON.stringify(String(r.body ?? '').slice(0, 200)).replaceAll('\n', ' '),
        ].join(','),
      ),
    ]
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'yeseeeooo-content.csv'
    a.click()
  }

  if (!workspaceId) {
    return (
      <div className="p-8 text-center">
        <p className="text-zinc-400">No workspace — start onboarding.</p>
        <Button className="mt-4" onClick={() => nav('/onboard')}>
          Onboard
        </Button>
      </div>
    )
  }

  const score = analytics?.weekly_seo_score as Record<string, unknown> | undefined

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header
        className="border-b border-zinc-800 px-4 py-4 md:px-8"
        style={{ borderBottomColor: `${brandColors.primary}44` }}
      >
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold">SEO & GEO Command</h1>
            <p className="text-xs text-zinc-500">
              Workspace {workspaceId.slice(0, 8)}…
              {wsStatus?.crawl_completed ? (
                <span className="ml-2 text-emerald-500/90">Crawl ready</span>
              ) : (
                <span className="ml-2 text-amber-500/90">Crawl required for agents</span>
              )}
              {wsStatus?.crawl_completed && wsStatus.pending_plan_items > 0 ? (
                <span className="ml-2 text-zinc-500">· {wsStatus.pending_plan_items} plan items</span>
              ) : null}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {!wsStatus?.crawl_completed ? (
              <Button
                variant="default"
                size="sm"
                disabled={queueCrawl.isPending}
                onClick={() => queueCrawl.mutate()}
              >
                Queue site crawl
              </Button>
            ) : null}
            <Button
              variant="secondary"
              size="sm"
              disabled={!wsStatus?.crawl_completed || triggerCycle.isPending}
              title="Runs the full pipeline (many model calls at once)"
              onClick={() => triggerCycle.mutate()}
            >
              Run full cycle
            </Button>
            <Button variant="outline" size="sm" onClick={exportCsv}>
              Export CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => nav('/brand')}>
              Brand report
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[220px_1fr] lg:px-8">
        <aside className="space-y-3">
          <p className="text-xs font-medium uppercase text-zinc-500">Agents</p>
          <p className="text-[10px] text-zinc-600">
            One model call per Run. Maya saves a plan; writers use it (or defaults). Crawl must finish first.
          </p>
          {AGENTS.map((a) => (
            <div
              key={a.name}
              className={`rounded-lg border px-2 py-2 text-sm ${
                agentFilter === a.name ? 'border-violet-500 bg-violet-950/30' : 'border-zinc-800'
              }`}
            >
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="flex min-w-0 flex-1 items-center gap-2 text-left"
                  onClick={() => setAgentFilter((f) => (f === a.name ? null : a.name))}
                >
                  <Avatar className="h-8 w-8 shrink-0">
                    <AvatarFallback style={{ backgroundColor: a.color, color: '#111' }}>{a.name[0]}</AvatarFallback>
                  </Avatar>
                  <div className="min-w-0">
                    <div className="font-medium">{a.name}</div>
                    <div className="truncate text-[10px] text-zinc-500">{a.role}</div>
                  </div>
                </button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  className="shrink-0 px-2 text-xs"
                  disabled={!wsStatus?.crawl_completed || runAgent.isPending}
                  onClick={() => runAgent.mutate(a.name)}
                >
                  Run
                </Button>
              </div>
            </div>
          ))}
        </aside>

        <main className="space-y-6">
          {runAgent.isError ? (
            <div className="rounded-md border border-red-900/60 bg-red-950/40 px-3 py-2 text-sm text-red-200">
              {(runAgent.error as Error)?.message ?? 'Agent run failed'}
            </div>
          ) : null}
          {queueCrawl.isError ? (
            <div className="rounded-md border border-red-900/60 bg-red-950/40 px-3 py-2 text-sm text-red-200">
              {(queueCrawl.error as Error)?.message ?? 'Crawl queue failed'}
            </div>
          ) : null}
          {score ? (
            <Card className="border-zinc-800">
              <CardHeader>
                <CardTitle className="text-base">Weekly SEO score</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-6">
                <div className="text-4xl font-bold text-white">{String(score.total ?? '—')}</div>
                <div className="grid flex-1 grid-cols-2 gap-2 text-xs md:grid-cols-5">
                  {Object.entries((score.breakdown as Record<string, number>) || {}).map(([k, v]) => (
                    <div key={k} className="rounded-md bg-zinc-900 p-2">
                      <div className="text-zinc-500">{k.replace(/_/g, ' ')}</div>
                      <div className="text-lg font-semibold">{v}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : null}

          <Tabs defaultValue="activity">
            <TabsList className="flex flex-wrap">
              <TabsTrigger value="activity">Activity</TabsTrigger>
              <TabsTrigger value="approvals">Approvals</TabsTrigger>
              <TabsTrigger value="keywords">Keywords</TabsTrigger>
              <TabsTrigger value="backlinks">Backlinks</TabsTrigger>
              <TabsTrigger value="geo">GEO</TabsTrigger>
              <TabsTrigger value="competitors">Competitors</TabsTrigger>
            </TabsList>

            <TabsContent value="activity" className="space-y-4">
              <Card className="border-zinc-800">
                <CardHeader>
                  <CardTitle className="text-base">Live agent stream</CardTitle>
                </CardHeader>
                <CardContent className="max-h-[420px] space-y-2 overflow-y-auto text-sm">
                  {filteredSse.length === 0 ? <p className="text-zinc-500">Waiting for events…</p> : null}
                  {filteredSse.map((e, i) => (
                    <div key={i} className="flex gap-3 rounded-lg border border-zinc-800/80 bg-zinc-900/40 p-2">
                      <Avatar className="h-8 w-8">
                        <AvatarFallback>{String(e.agent ?? '•').slice(0, 1)}</AvatarFallback>
                      </Avatar>
                      <div>
                        <div className="font-medium text-zinc-200">{String(e.type ?? 'event')}</div>
                        <div className="text-xs text-zinc-500">
                          {String(e.agent ?? '')} {e.platform ? `· ${String(e.platform)}` : ''} · {String(e.at ?? '')}
                        </div>
                      </div>
                    </div>
                  ))}
                  <Separator className="my-4" />
                  <p className="text-xs text-zinc-500">Server timeline (paginated)</p>
                  {(activityData?.items ?? []).map((log) => (
                    <div key={String(log.id)} className="text-xs text-zinc-400">
                      <span className="text-zinc-200">{String(log.agent_name)}</span> · {String(log.action_type)} ·{' '}
                      {String(log.created_at)}
                    </div>
                  ))}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="approvals">
              <div className="grid gap-4 md:grid-cols-2">
                {approvalDrafts.length === 0 ? <p className="text-zinc-500">No drafts in queue.</p> : null}
                {approvalDrafts.map((d) => (
                  <Card key={String(d.id)} className="border-zinc-800">
                    <CardHeader>
                      <div className="flex flex-wrap items-center gap-2">
                        <CardTitle className="text-sm">{String(d.title ?? 'Untitled')}</CardTitle>
                        <Badge>{String(d.agent_name)}</Badge>
                        <Badge className="border border-zinc-600 bg-transparent">{String(d.platform)}</Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm text-zinc-400">
                      {expandedDraftId === String(d.id) ? (
                        <div className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-md border border-zinc-800 bg-zinc-900/40 p-3 text-zinc-300">
                          {String(d.body ?? '')}
                        </div>
                      ) : (
                        <p>{String(d.body ?? '').slice(0, 200)}…</p>
                      )}
                      <div className="flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            setExpandedDraftId((curr) => (curr === String(d.id) ? null : String(d.id)))
                          }
                        >
                          {expandedDraftId === String(d.id) ? 'Collapse' : 'View full'}
                        </Button>
                        <Button
                          size="sm"
                          disabled={isQuotaFallbackDraft(d)}
                          onClick={() => approve.mutate(String(d.id))}
                          title={isQuotaFallbackDraft(d) ? 'Retry generation when Gemini quota is available.' : undefined}
                        >
                          Approve
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => reject.mutate(String(d.id))}>
                          Reject
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
              {approvalDrafts.length > 1 ? (
                <Button
                  className="mt-4"
                  variant="outline"
                  onClick={() =>
                    approvalDrafts.filter((d) => !isQuotaFallbackDraft(d)).forEach((d) => approve.mutate(String(d.id)))
                  }
                >
                  Bulk approve visible
                </Button>
              ) : null}
            </TabsContent>

            <TabsContent value="keywords" className="space-y-4">
              <div className="flex gap-2">
                {(['7d', '30d', '90d'] as const).map((r) => (
                  <Button key={r} size="sm" variant={range === r ? 'default' : 'secondary'} onClick={() => setRange(r)}>
                    {r}
                  </Button>
                ))}
              </div>
              <Card className="border-zinc-800">
                <CardContent className="h-72 pt-6">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid stroke="#27272a" />
                      <XAxis dataKey="date" stroke="#71717a" tick={{ fontSize: 10 }} />
                      <YAxis stroke="#71717a" reversed domain={['dataMax + 5', 1]} tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #3f3f46' }} />
                      <Legend />
                      {(chartData[0] ? Object.keys(chartData[0]).filter((k) => k !== 'date') : [])
                        .slice(0, 5)
                        .map((k, i) => (
                          <Line
                            key={k}
                            type="monotone"
                            dataKey={k}
                            stroke={['#a78bfa', '#34d399', '#f472b6', '#fb923c', '#38bdf8'][i % 5]}
                            dot={false}
                          />
                        ))}
                    </LineChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
              <div className="overflow-x-auto rounded-lg border border-zinc-800">
                <table className="w-full text-left text-sm">
                  <thead className="bg-zinc-900 text-xs text-zinc-500">
                    <tr>
                      <th className="p-2">Keyword</th>
                      <th className="p-2">Rank</th>
                      <th className="p-2">Δ</th>
                      <th className="p-2">Volume</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(keywordsData?.items ?? []).slice(0, 20).map((r) => (
                      <tr key={String(r.id)} className="border-t border-zinc-800">
                        <td className="p-2">{String(r.keyword)}</td>
                        <td className="p-2">{String(r.position ?? '—')}</td>
                        <td className="p-2">
                          {r.previous_position != null && r.position != null
                            ? Number(r.previous_position) - Number(r.position)
                            : '—'}
                        </td>
                        <td className="p-2">{String(r.search_volume ?? '—')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </TabsContent>

            <TabsContent value="backlinks">
              <Card className="border-zinc-800">
                <CardHeader>
                  <CardTitle className="text-base">Total {backlinksData?.total ?? 0}</CardTitle>
                </CardHeader>
                <CardContent className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs text-zinc-500">
                      <tr>
                        <th className="p-2">Source</th>
                        <th className="p-2">DA</th>
                        <th className="p-2">Target</th>
                        <th className="p-2">Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(backlinksData?.items ?? []).map((r) => (
                        <tr key={String(r.id)} className="border-t border-zinc-800">
                          <td className="max-w-[200px] truncate p-2">{String(r.source_url)}</td>
                          <td className="p-2">{String(r.domain_authority ?? '—')}</td>
                          <td className="max-w-[200px] truncate p-2">{String(r.target_url)}</td>
                          <td className="p-2">{String(r.discovered_at).slice(0, 10)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="geo" className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {(['all', 'chatgpt', 'perplexity', 'google_sge'] as const).map((e) => (
                  <Button key={e} size="sm" variant={geoEngine === e ? 'default' : 'secondary'} onClick={() => setGeoEngine(e)}>
                    {e}
                  </Button>
                ))}
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                {(geoData?.items ?? [])
                  .filter((g) => geoEngine === 'all' || String(g.engine) === geoEngine)
                  .map((g) => (
                    <Card key={String(g.id)} className="border-zinc-800">
                      <CardHeader>
                        <CardTitle className="text-sm uppercase text-zinc-400">{String(g.engine)}</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2 text-sm">
                        <p className="font-medium text-zinc-200">Query: {String(g.query_used)}</p>
                        <p className="text-zinc-400">{String(g.mention_snippet)}</p>
                        <p className="text-xs text-zinc-500">
                          confidence {String(g.confidence_score)} · {String(g.detected_at)}
                        </p>
                      </CardContent>
                    </Card>
                  ))}
              </div>
            </TabsContent>

            <TabsContent value="competitors">
              <div className="grid gap-4 md:grid-cols-3">
                {(compData?.items ?? []).map((c, i) => (
                  <Card key={i} className="border-zinc-800">
                    <CardHeader>
                      <CardTitle className="text-base">{String(c.competitor)}</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-zinc-400">
                      <p className="text-xs text-violet-300">Keyword overlap</p>
                      <ul className="list-disc pl-4">
                        {(c.shared_keywords as string[]).map((k) => (
                          <li key={k}>{k}</li>
                        ))}
                      </ul>
                      <p className="mt-2 text-xs text-zinc-500">Content gap</p>
                      <ul className="list-disc pl-4">
                        {(c.gap_topics as string[]).map((k) => (
                          <li key={k}>{k}</li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </main>
      </div>
    </div>
  )
}
