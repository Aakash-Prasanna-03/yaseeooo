# yeseeeooo

`yeseeeooo` is an AI content automation app for small teams.
It helps a user:

1. connect/sign in with Supabase auth,
2. onboard a brand/workspace,
3. crawl brand context,
4. generate a content plan + drafts with multiple agents,
5. review/approve and publish content,
6. monitor activity and basic SEO/GEO signals.

## What this project includes

- `frontend/`: React + Vite single-page app (auth, onboarding, dashboard, reports)
- `backend/`: FastAPI API + async/background task execution
- `supabase/migrations/`: SQL schema/migration files for the app database
- `supabase/scripts/`: utility SQL scripts (for example reset app data)

## Current readiness

This repository is best treated as a **working MVP / early beta**.

- Core product flow exists end-to-end (auth -> onboarding -> crawl -> agent generation -> approvals/publish).
- Supabase-backed auth and Postgres integration are in place.
- Background processing and SSE activity streaming are implemented.
- Some integrations still have placeholder/demo behavior depending on configuration.
- Use for internal testing/dev and pilot usage first; harden before production scale.

## How it works

### High-level architecture

- **Frontend (React/Vite):** user experience, route protection, Supabase session handling.
- **Backend (FastAPI):** API endpoints for onboarding, crawl/cycle triggers, content and analytics.
- **Agent pipeline (LangGraph):** multi-step content cycle (planning, writing, GEO layer, publishing, monitoring).
- **Database (Supabase Postgres):** workspaces, brand profiles, drafts, logs, analytics entities.
- **Redis/Celery:** async execution for crawl and content cycle jobs.

### Main user flow

1. User signs in via Supabase.
2. Frontend syncs identity to backend.
3. User completes onboarding (`workspace` + brand context).
4. Crawl runs and enriches brand profile memory.
5. Agents create content plan and drafts.
6. User approves/rejects drafts.
7. Approved drafts publish through configured integrations.
8. Dashboard/report pages read analytics/logs from backend APIs.

## Quick start

### 1) Prerequisites

- Node.js 20+
- Python 3.11+
- Docker (optional, for local Postgres/Redis)

### 2) Configure environment files

Create environment files from examples:

- `backend/.env` from `backend/.env.example`
- `frontend/.env.local` from `frontend/.env.example` (if present)

Important backend variables:

- `DATABASE_URL`
- `SUPABASE_JWT_SECRET`
- `REDIS_URL`
- `LLM_PROVIDER` plus provider-specific API keys/models

For hosted Supabase setup, migrations, and troubleshooting, see `SUPABASE_SETUP.md`.

### 3) Install dependencies

Frontend:

```bash
cd frontend
npm install
```

Backend:

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4) Start infrastructure (if needed)

If you are using local Postgres/Redis:

```bash
docker compose up -d postgres redis
```

If you use hosted Supabase for Postgres, you can run only Redis locally:

```bash
docker compose up -d redis
```

### 5) Run backend and frontend

Backend API:

```bash
cd backend
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm run dev
```

Default dev URLs:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`

## Running async workers

The app can fall back to inline execution in some paths, but for realistic async behavior run workers.

Typical local pattern:

- Keep backend API running.
- Run worker process(es) using the same `backend/.env` values (`DATABASE_URL`, `REDIS_URL`, etc.).

If your team has a standard worker command in scripts/process manager, use that as source of truth.

## LLM provider configuration

Set `LLM_PROVIDER` to one of:

- `gemini`
- `openai`
- `ollama`

Tiered model routing is controlled by `*_PRO_MODEL` and `*_FLASH_MODEL` variables in `backend/.env`.

## Useful scripts and docs

- `SUPABASE_SETUP.md`: full Supabase setup + migration flow
- `supabase/scripts/reset_app_data.sql`: wipe app tables while keeping Supabase auth users
- `backend/scripts/check_db.py`: quick DB connectivity check

## Troubleshooting

- **401 / token errors:** verify `SUPABASE_JWT_SECRET` matches your Supabase project JWT secret.
- **Database SSL/connection errors:** ensure `DATABASE_URL` has valid host/password and includes SSL params for hosted DB.
- **No background progress:** verify Redis is reachable and worker processes are running.
- **Empty dashboard data:** ensure migrations ran on the same database referenced by `DATABASE_URL`.

## Tech stack

- React + TypeScript + Vite
- FastAPI + asyncpg
- LangGraph for agent orchestration
- Supabase Auth + Postgres
- Redis + Celery (task queue)
