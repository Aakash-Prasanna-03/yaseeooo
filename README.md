# yeseeeooo

Content automation app with:
- `frontend/`: React + Vite UI
- `backend/`: FastAPI API + async workers
- `supabase/migrations/`: database schema and SQL changes

## Quick Start

### 1) Prerequisites
- Node.js 20+
- Python 3.11+
- Docker (for local Postgres/Redis if needed)

### 2) Configure environment files

Create env files from examples:

- `backend/.env` from `backend/.env.example`
- `frontend/.env.local` from `frontend/.env.example` (if present)

Required backend values are documented in `backend/.env.example`, including:
- `DATABASE_URL`
- `SUPABASE_JWT_SECRET`
- `LLM_PROVIDER` + provider-specific model/API keys

For full hosted Supabase setup and migration instructions, see `SUPABASE_SETUP.md`.

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

### 4) Start local services (optional)

If using local infrastructure instead of hosted services:

```bash
docker compose up -d postgres redis
```

### 5) Run the app

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

## Notes

- Redis is used for Celery-backed background tasks.
- LLM routing supports `gemini`, `openai`, or `ollama` via `LLM_PROVIDER`.
- Tiered model settings are controlled with `*_PRO_MODEL` and `*_FLASH_MODEL` env vars.
