-- yeseeeooo core schema + RLS (Supabase)
-- Assumes auth.users exists. Sync app user row via API or trigger.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS public.users (
  id UUID PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  email TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  plan_tier TEXT NOT NULL DEFAULT 'free' CHECK (plan_tier IN ('free', 'starter', 'growth', 'agency'))
);

CREATE TABLE IF NOT EXISTS public.workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  business_name TEXT NOT NULL,
  business_description TEXT,
  website_url TEXT,
  target_audience TEXT,
  primary_goal TEXT,
  platforms TEXT[] NOT NULL DEFAULT '{}',
  approval_mode BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  trial_ends_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS public.brand_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces (id) ON DELETE CASCADE,
  colors JSONB NOT NULL DEFAULT '{}',
  typography TEXT,
  tone_of_voice TEXT,
  keywords TEXT[] NOT NULL DEFAULT '{}',
  competitors TEXT[] NOT NULL DEFAULT '{}',
  social_handles JSONB NOT NULL DEFAULT '{}',
  industry TEXT,
  cta_language TEXT,
  content_structure TEXT,
  raw_crawl_data JSONB NOT NULL DEFAULT '{}',
  crawled_at TIMESTAMPTZ,
  version INT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS public.content_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces (id) ON DELETE CASCADE,
  agent_name TEXT NOT NULL,
  content_type TEXT NOT NULL CHECK (content_type IN ('blog', 'linkedin', 'reddit', 'twitter', 'quora', 'geo', 'email')),
  title TEXT,
  body TEXT NOT NULL DEFAULT '',
  platform TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'awaiting_approval', 'approved', 'rejected', 'published', 'failed')),
  content_hash TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at TIMESTAMPTZ,
  scheduled_for TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.agent_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces (id) ON DELETE CASCADE,
  agent_name TEXT NOT NULL,
  action_type TEXT NOT NULL,
  platform TEXT,
  content_id UUID REFERENCES public.content_drafts (id) ON DELETE SET NULL,
  token_count INT,
  outcome_metric JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.keyword_rankings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces (id) ON DELETE CASCADE,
  keyword TEXT NOT NULL,
  position INT,
  previous_position INT,
  search_volume INT,
  checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.backlinks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces (id) ON DELETE CASCADE,
  source_url TEXT NOT NULL,
  target_url TEXT NOT NULL,
  domain_authority INT,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.geo_mentions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces (id) ON DELETE CASCADE,
  engine TEXT NOT NULL CHECK (engine IN ('chatgpt', 'perplexity', 'google_sge')),
  query_used TEXT NOT NULL,
  mention_snippet TEXT,
  confidence_score NUMERIC(5, 4),
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.content_cycles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces (id) ON DELETE CASCADE,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
  pieces_generated INT NOT NULL DEFAULT 0,
  pieces_published INT NOT NULL DEFAULT 0,
  summary JSONB NOT NULL DEFAULT '{}'
);

-- PGVector fallback: store embeddings as JSONB (no extension required)
CREATE TABLE IF NOT EXISTS public.brand_memory_embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces (id) ON DELETE CASCADE,
  chunk_text TEXT NOT NULL,
  embedding JSONB NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Billing usage tracking (Phase 5)
CREATE TABLE IF NOT EXISTS public.billing_usage (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  pieces_used INT NOT NULL DEFAULT 0,
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  UNIQUE (user_id, period_start)
);

CREATE INDEX IF NOT EXISTS idx_workspaces_user ON public.workspaces (user_id);
CREATE INDEX IF NOT EXISTS idx_brand_profiles_ws ON public.brand_profiles (workspace_id);
CREATE INDEX IF NOT EXISTS idx_content_drafts_ws ON public.content_drafts (workspace_id);
CREATE INDEX IF NOT EXISTS idx_agent_logs_ws ON public.agent_logs (workspace_id);
CREATE INDEX IF NOT EXISTS idx_keyword_rankings_ws ON public.keyword_rankings (workspace_id);
CREATE INDEX IF NOT EXISTS idx_backlinks_ws ON public.backlinks (workspace_id);
CREATE INDEX IF NOT EXISTS idx_geo_mentions_ws ON public.geo_mentions (workspace_id);
CREATE INDEX IF NOT EXISTS idx_content_cycles_ws ON public.content_cycles (workspace_id);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brand_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.keyword_rankings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.backlinks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.geo_mentions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content_cycles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brand_memory_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.billing_usage ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_own_row" ON public.users
  FOR ALL USING (auth.uid() = id);

CREATE POLICY "workspaces_by_owner" ON public.workspaces
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "brand_profiles_by_workspace" ON public.brand_profiles
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.workspaces w WHERE w.id = workspace_id AND w.user_id = auth.uid())
  );

CREATE POLICY "content_drafts_by_workspace" ON public.content_drafts
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.workspaces w WHERE w.id = workspace_id AND w.user_id = auth.uid())
  );

CREATE POLICY "agent_logs_by_workspace" ON public.agent_logs
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.workspaces w WHERE w.id = workspace_id AND w.user_id = auth.uid())
  );

CREATE POLICY "keyword_rankings_by_workspace" ON public.keyword_rankings
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.workspaces w WHERE w.id = workspace_id AND w.user_id = auth.uid())
  );

CREATE POLICY "backlinks_by_workspace" ON public.backlinks
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.workspaces w WHERE w.id = workspace_id AND w.user_id = auth.uid())
  );

CREATE POLICY "geo_mentions_by_workspace" ON public.geo_mentions
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.workspaces w WHERE w.id = workspace_id AND w.user_id = auth.uid())
  );

CREATE POLICY "content_cycles_by_workspace" ON public.content_cycles
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.workspaces w WHERE w.id = workspace_id AND w.user_id = auth.uid())
  );

CREATE POLICY "brand_memory_by_workspace" ON public.brand_memory_embeddings
  FOR ALL USING (
    EXISTS (SELECT 1 FROM public.workspaces w WHERE w.id = workspace_id AND w.user_id = auth.uid())
  );

CREATE POLICY "billing_usage_by_user" ON public.billing_usage
  FOR ALL USING (auth.uid() = user_id);
