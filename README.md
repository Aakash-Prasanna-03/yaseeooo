# yeseeeooo

AI-powered content automation platform that helps teams turn brand context into planned, generated, reviewed, and publish-ready content.

---

## 1. Project Overview

`yeseeeooo` automates content operations for SEO/GEO-focused teams using an orchestrated multi-agent pipeline.

### Main objective

The project reduces manual effort in content planning, drafting, optimization, and publishing by combining:

- a guided frontend workflow,
- backend APIs and async processing,
- a graph-based agent pipeline,
- local LLM reasoning through Ollama.

### Real-world problem it solves

Most teams struggle with:

- inconsistent content planning,
- slow content production cycles,
- lack of repeatable optimization workflows,
- fragmented tools for writing, review, and execution.

This system centralizes the process and runs it as a structured, repeatable flow.

### How users interact with the system

Users typically:

1. sign in and create a workspace,
2. provide business/brand details,
3. trigger crawl and content generation workflows,
4. review and approve drafts,
5. track outcomes in dashboard and activity views.

### End-to-end workflow summary

User input from the UI is sent to FastAPI endpoints, which trigger LangGraph workflows.  
LangGraph coordinates agent nodes built with LangChain.  
LangChain calls locally hosted Ollama models for reasoning/generation.  
Results are saved in Postgres and returned/streamed back to the frontend for display.

---

## 2. Key Features

- **Brand onboarding workflow** for workspace-specific context capture.
- **Crawl-triggered content readiness** before full generation cycles.
- **Graph-orchestrated multi-agent pipeline** for planning, writing, optimization, and publishing.
- **Agent-based content planning** (topic and platform-aware plan creation).
- **Parallel draft generation** for faster throughput.
- **Approval/rejection flow** for human-in-the-loop control.
- **Activity streaming and logs** for visibility into agent actions.
- **Analytics/reporting endpoints** for content and performance snapshots.
- **Local LLM execution via Ollama** for privacy-friendly and offline-capable development.

---

## 3. Tech Stack

### Core AI/Orchestration

- **LangGraph**: workflow orchestration and state transitions across agent nodes.
- **LangChain**: prompt construction, message handling, model abstraction, and tool-compatible pipelines.
- **Ollama**: local model execution (`LLM_PROVIDER=ollama`), default env example uses `qwen2.5:7b` for both pro/flash tiers (can be switched to Mistral/LLaMA family models).

### Application

- **Backend**: FastAPI, async Python, asyncpg, Celery-compatible task flow.
- **Frontend**: React + TypeScript + Vite.
- **Data/Infra**: Postgres (Supabase-hosted or local), Redis for background job queueing, Docker for local services.

---

## 4. System Architecture

At a high level, the system is split into:

1. **Frontend application** (user input, workflow navigation, result presentation),
2. **FastAPI backend** (request validation, orchestration triggers, persistence),
3. **LangGraph workflow engine** (stateful node execution and transitions),
4. **LangChain-powered agent layer** (prompting, reasoning, model invocation),
5. **Ollama runtime** (local LLM responses),
6. **Database + queue layer** (Postgres + Redis).

### LangGraph workflow design

LangGraph manages the content cycle as a directed workflow with nodes such as:

- startup/context loading,
- brand context resolution,
- trend/content planning,
- parallel writer execution,
- review gate,
- optimization layer,
- publication and monitoring,
- feedback/summary.

Each node reads/writes structured workflow state, and conditional transitions control paths such as approval-required vs. auto-continue.

### LangChain integration

LangChain is used inside node logic to:

- assemble agent-specific system/user prompts,
- run role-based agent tasks,
- normalize model outputs,
- carry reasoning context per execution step.

### Ollama local inference flow

When `LLM_PROVIDER=ollama`, the backend invokes local models through LangChain's Ollama chat interface using:

- `OLLAMA_BASE_URL` (default local service URL),
- tiered model selection (`OLLAMA_PRO_MODEL`, `OLLAMA_FLASH_MODEL`).

Model output is parsed, post-processed, and persisted as draft/content artifacts before API responses are returned.

---

## 5. Backend Details

Backend code lives in `backend/` and is centered on FastAPI request handlers and workflow services.

### Responsibilities

- expose REST endpoints for auth sync, onboarding, crawl, content cycle, drafts, approvals, analytics, and activity;
- validate user/workspace ownership and request payloads;
- trigger async tasks for crawling and content cycles;
- call LangGraph workflow services for orchestrated agent execution;
- persist outputs into Postgres tables;
- stream updates via SSE endpoints.

### API and request handling

The API layer:

- receives frontend requests,
- checks auth context,
- maps requests to domain operations (e.g., run single agent, trigger cycle, approve draft),
- returns structured JSON responses suitable for UI rendering.

### LangGraph + LangChain + Ollama interaction

In content-generation paths:

1. endpoint/service starts workflow execution,
2. LangGraph node functions run in sequence (or parallel where applicable),
3. nodes call LangChain agents,
4. LangChain invokes Ollama model locally,
5. outputs are normalized and stored.

### Data flow and response formatting

Generated content, agent logs, cycle states, and analytics metrics are stored in Postgres and surfaced through typed JSON responses for the frontend.

---

## 6. Frontend Details

Frontend code lives in `frontend/` and uses React + Vite for a route-based UI.

### Structure

- page-level routes for auth, onboarding, crawl waiting, reveal, dashboard, and reports;
- API client abstraction for backend communication;
- auth-aware route guarding for protected views;
- state-driven rendering for loading, processing, success, and error states.

### Backend communication

The frontend sends JSON requests to FastAPI endpoints and attaches auth headers when sessions are available. It consumes:

- synchronous JSON responses for standard operations,
- stream/event updates for long-running workflow visibility.

### User interaction flow

1. **Input submission**: users submit onboarding/workspace/action requests.
2. **Processing state**: UI shows in-progress states while backend workflows run.
3. **Output display**: generated drafts, status updates, and analytics are rendered in dashboard/reporting screens.

---

## 7. End-to-End Workflow

User Input -> Frontend -> Backend API -> LangGraph Workflow -> LangChain Agent -> Ollama Model -> Response -> Frontend Display

Step-by-step:

1. User enters request/context in the React UI.
2. Frontend calls FastAPI endpoint.
3. Backend validates request and loads workspace/brand context.
4. Backend starts LangGraph workflow.
5. Workflow nodes call LangChain agent logic.
6. LangChain invokes local Ollama model for generation/reasoning.
7. Node outputs are aggregated and persisted.
8. Backend returns status/content payload to frontend.
9. Frontend displays drafts, logs, and analytics for user action.

---

## 8. Installation & Setup

### Prerequisites

- Node.js 20+
- Python 3.11+
- Docker (recommended for local Postgres/Redis)
- Ollama installed locally

### 1) Clone repository

```bash
git clone <your-repo-url>
cd yeseeeooo
```

### 2) Configure environment files

Create:

- `backend/.env` from `backend/.env.example`
- `frontend/.env.local` from `frontend/.env.example` (if present)

Set backend LLM config for local inference:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_PRO_MODEL=qwen2.5:7b
OLLAMA_FLASH_MODEL=qwen2.5:7b
```

Also configure:

- `DATABASE_URL`
- `REDIS_URL`
- `SUPABASE_JWT_SECRET`

### 3) Install dependencies

Frontend:

```bash
cd frontend
npm install
```

Backend:

```bash
cd ../backend
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4) Set up Ollama and pull model

Start Ollama and pull the model configured in `.env`:

```bash
ollama pull qwen2.5:7b
```

You can replace with another compatible local model (for example Mistral or LLaMA-family variants) as long as the env vars match.

### 5) Start infrastructure

If running local infra:

```bash
docker compose up -d postgres redis
```

If using hosted Postgres, run Redis only:

```bash
docker compose up -d redis
```

### 6) Run backend

```bash
cd backend
uvicorn app.main:app --reload
```

### 7) Run frontend

```bash
cd frontend
npm run dev
```

### 8) Open the app

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

---

## 9. Future Improvements

- Add queue observability dashboard and workflow tracing.
- Introduce retry/backoff policies per workflow node and model call.
- Expand agent toolset for richer research and content grounding.
- Add role-based permissions and team collaboration workflows.
- Improve publishing connectors and delivery guarantees.
- Add evaluation pipelines for draft quality and factual consistency.
- Add autoscaling worker deployment patterns for high-throughput workloads.

---

## 10. Conclusion

`yeseeeooo` provides a practical blueprint for agentic content automation: a React frontend, FastAPI backend, LangGraph orchestration, LangChain agent runtime, and local Ollama inference.  
It demonstrates how to build a developer-friendly, extensible, and production-oriented workflow where human review and automated generation work together in one system.
