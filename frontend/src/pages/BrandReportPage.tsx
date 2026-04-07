import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { apiFetch } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function BrandReportPage() {
  const nav = useNavigate()
  const { workspaceId, brandColors } = useWorkspaceStore()
  const { data } = useQuery({
    queryKey: ['brand-profile', workspaceId],
    enabled: !!workspaceId,
    queryFn: () => apiFetch(`/api/brand-profile/${workspaceId}`) as Promise<{ profile: Record<string, unknown> | null }>,
  })
  const p = data?.profile

  if (!workspaceId) {
    return (
      <div className="p-8 text-center">
        <Button onClick={() => nav('/onboard')}>Onboard first</Button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-white">Brand intelligence</h1>
        <Button variant="secondary" onClick={() => nav('/dashboard')}>
          Dashboard
        </Button>
      </div>
      {!p ? (
        <p className="text-zinc-500">Crawl in progress…</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <Card className="border-zinc-800" style={{ borderColor: `${brandColors.primary}55` }}>
            <CardHeader>
              <CardTitle className="text-base">Colors</CardTitle>
            </CardHeader>
            <CardContent className="flex gap-2 text-sm">
              {Object.entries((p.colors as Record<string, string>) || {}).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2">
                  <span className="h-6 w-6 rounded-full border border-zinc-700" style={{ background: v }} />
                  {k}
                </div>
              ))}
            </CardContent>
          </Card>
          <Card className="border-zinc-800">
            <CardHeader>
              <CardTitle className="text-base">Typography</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-zinc-400">{String(p.typography ?? '—')}</CardContent>
          </Card>
          <Card className="border-zinc-800 md:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">Tone of voice</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-zinc-300">{String(p.tone_of_voice ?? '—')}</CardContent>
          </Card>
          <Card className="border-zinc-800">
            <CardHeader>
              <CardTitle className="text-base">Keywords</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-1">
              {(p.keywords as string[] | undefined)?.map((k) => (
                <span key={k} className="rounded bg-zinc-800 px-2 py-0.5 text-xs">
                  {k}
                </span>
              ))}
            </CardContent>
          </Card>
          <Card className="border-zinc-800">
            <CardHeader>
              <CardTitle className="text-base">Industry</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-zinc-400">{String(p.industry ?? '—')}</CardContent>
          </Card>
          <Card className="border-zinc-800 md:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">CTA language</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-zinc-300">{String(p.cta_language ?? '—')}</CardContent>
          </Card>
          <Card className="border-zinc-800 md:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">Content structure</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-zinc-400">{String(p.content_structure ?? '—')}</CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
