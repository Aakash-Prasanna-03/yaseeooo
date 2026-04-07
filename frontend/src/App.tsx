import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { supabase } from '@/lib/supabase'
import { apiFetch } from '@/api/client'
import { AuthPage } from '@/pages/AuthPage'
import { OnboardPage } from '@/pages/OnboardPage'
import { CrawlWaitPage } from '@/pages/CrawlWaitPage'
import { AgentRevealPage } from '@/pages/AgentRevealPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { BrandReportPage } from '@/pages/BrandReportPage'

function SessionSync() {
  useEffect(() => {
    if (!supabase) return
    void supabase.auth.getSession().then(({ data }) => {
      const u = data.session?.user
      if (u?.id) {
        localStorage.setItem('yeseee_dev_user_id', u.id)
        void apiFetch('/api/auth/sync', {
          method: 'POST',
          body: JSON.stringify({ email: u.email }),
        }).catch(() => {})
      }
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_e, session) => {
      const u = session?.user
      if (u?.id) {
        localStorage.setItem('yeseee_dev_user_id', u.id)
        void apiFetch('/api/auth/sync', {
          method: 'POST',
          body: JSON.stringify({ email: u.email }),
        }).catch(() => {})
      }
    })
    return () => sub.subscription.unsubscribe()
  }, [])
  return null
}

export default function App() {
  return (
    <BrowserRouter>
      <SessionSync />
      <Routes>
        <Route path="/" element={<Navigate to="/auth" replace />} />
        <Route path="/auth" element={<AuthPage />} />
        <Route path="/onboard" element={<OnboardPage />} />
        <Route path="/crawl" element={<CrawlWaitPage />} />
        <Route path="/reveal" element={<AgentRevealPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/brand" element={<BrandReportPage />} />
        <Route path="*" element={<Navigate to="/auth" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
