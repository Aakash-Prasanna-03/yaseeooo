-- Stores Maya's latest content plan for step-by-step agent runs (one agent per request).
ALTER TABLE public.workspaces
ADD COLUMN IF NOT EXISTS pending_content_plan JSONB NOT NULL DEFAULT '[]'::jsonb;
