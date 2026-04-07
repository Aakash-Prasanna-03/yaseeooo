# Implementation assumptions (yeseeeooo)

- **Monorepo**: `frontend/` (Vercel) and `backend/` (Railway). Local URLs: `http://localhost:3000`, `http://localhost:8000` (Vite dev server proxies `/api` to the backend).
- **Supabase**: `public.users` is synced from `auth.users` via app logic on first session (`POST /api/auth/sync`) or a DB trigger you add in the Supabase dashboard; migrations ship the `public` tables and RLS only.
- **Secrets**: DataForSEO, Ahrefs, Reddit (PRAW), LinkedIn, Medium, WordPress, Pinecone, Gemini, Stripe, PostHog, Sentry are optional at runtime; missing keys yield mock or no-op behavior so local/staging boots without vendor accounts.
- **Quora**: Playwright automation is implemented as a **stub** that logs intent and returns a simulated result unless `QUORA_AUTOMATION_ENABLED=true` and credentials are configured (fragile and account-dependent).
- **GEO monitoring**: Real ChatGPT/Perplexity/SGE scraping is not performed without explicit API/browser automation contracts; the pipeline records **structured placeholders** and demo rows when `GEO_MONITORING_MOCK=true` (default in dev).
- **React**: Scaffold originally pinned React 19 by Vite; production stack targets **React 18** — `package.json` pins `react@18` / `react-dom@18`.
- **Staging/production deploys**: CI workflows and `vercel.json` / Railway are wired; actual Vercel/Railway project linking and secrets are done in those dashboards.
- **Trial**: `trial_ends_at` is set to 14 days from workspace creation in `/api/onboard`; billing enforcement is Stripe Phase 5 middleware when `STRIPE_SECRET_KEY` is set.
- **LangGraph node IDs vs. spec**: The 10 logical steps map to nodes `startup` → `brand_context` → `trend_analysis` → `content_planning` → `writers_parallel` → `review_gate` → (`geo_layer` → `publication` → `monitoring` | `feedback_loop` if approval pause) → `feedback_loop` → END. Names differ from prose labels to avoid clashing with state keys (`trends`, `drafts`, etc.).
- **Grafana / infra metrics**: No bundled Grafana dashboards in-repo; run Grafana on Railway or a sidecar and scrape Redis/Celery/FastAPI metrics per your platform docs.
