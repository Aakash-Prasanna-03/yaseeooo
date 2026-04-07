from __future__ import annotations

from app.integrations import gemini_langchain_patch

gemini_langchain_patch.apply()

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, List, Optional

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import database as db
from app.auth_deps import CurrentUserId
from app.config import get_settings
from app import crud
from app.middleware.billing import BillingLimitMiddleware
from app.sse_broker import broker
from app.tasks import crawl_workspace_task, trigger_cycle_task

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None


class SyncUserBody(BaseModel):
    email: Optional[str] = None


class OnboardBody(BaseModel):
    business_name: str
    business_description: str
    website_url: str
    competitors: List[str] = Field(default_factory=list)
    target_audience: str
    platforms: List[str]
    primary_goal: str


class TriggerCycleBody(BaseModel):
    workspace_id: str


class RunAgentBody(BaseModel):
    workspace_id: str
    agent: str


def _queue_crawl(workspace_id: str) -> None:
    try:
        crawl_workspace_task.delay(workspace_id)
    except Exception:
        asyncio.create_task(_run_crawl_inline(workspace_id))


def _queue_cycle(workspace_id: str) -> None:
    try:
        trigger_cycle_task.delay(workspace_id)
    except Exception:
        asyncio.create_task(_run_cycle_inline(workspace_id))


async def _run_crawl_inline(workspace_id: str) -> None:
    from app.services import crawl_worker

    await crawl_worker.run_crawl(uuid.UUID(workspace_id))


async def _run_cycle_inline(workspace_id: str) -> None:
    from app.graph.pipeline import run_content_cycle

    await run_content_cycle(workspace_id)


def create_app() -> FastAPI:
    s = get_settings()
    if s.sentry_dsn and sentry_sdk:
        sentry_sdk.init(dsn=s.sentry_dsn, traces_sample_rate=0.1)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await db.close_pool()

    app = FastAPI(title="yeseeeooo API", version="0.1.0", lifespan=lifespan)
    origins = [o.strip() for o in s.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(BillingLimitMiddleware)

    @app.post("/api/auth/sync")
    async def auth_sync(payload: SyncUserBody, user_id: CurrentUserId):
        await crud.upsert_user(user_id, payload.email)
        return {"ok": True, "user_id": str(user_id)}

    @app.post("/api/onboard")
    async def onboard(payload: OnboardBody, user_id: CurrentUserId):
        await crud.upsert_user(user_id, None)
        wid = await crud.create_workspace(
            user_id,
            payload.business_name,
            payload.business_description,
            payload.website_url,
            payload.target_audience,
            payload.primary_goal,
            payload.platforms,
            payload.competitors or None,
        )
        _queue_crawl(str(wid))
        return {"workspace_id": str(wid)}

    @app.post("/api/crawl")
    async def crawl(workspace_id: str, user_id: CurrentUserId):
        ws = uuid.UUID(workspace_id)
        row = await db.fetch_one("SELECT user_id FROM workspaces WHERE id = $1", ws)
        if not row or row["user_id"] != user_id:
            raise HTTPException(404, "Workspace not found")
        _queue_crawl(str(ws))
        return {"status": "queued"}

    @app.get("/api/brand-profile/{workspace_id}")
    async def brand_profile(workspace_id: str, user_id: CurrentUserId):
        ws = uuid.UUID(workspace_id)
        row = await db.fetch_one("SELECT user_id FROM workspaces WHERE id = $1", ws)
        if not row or row["user_id"] != user_id:
            raise HTTPException(404, "Workspace not found")
        prof = await db.fetch_one(
            """
            SELECT * FROM brand_profiles WHERE workspace_id = $1
            ORDER BY version DESC, crawled_at DESC NULLS LAST LIMIT 1
            """,
            ws,
        )
        if not prof:
            return {"workspace_id": workspace_id, "profile": None}
        return {"workspace_id": workspace_id, "profile": dict(prof)}

    @app.get("/api/workspace/{workspace_id}/status")
    async def workspace_status(workspace_id: str, user_id: CurrentUserId):
        ws = uuid.UUID(workspace_id)
        row = await db.fetch_one("SELECT user_id FROM workspaces WHERE id = $1", ws)
        if not row or row["user_id"] != user_id:
            raise HTTPException(404, "Workspace not found")
        crawl_done = await crud.has_completed_crawl(ws)
        plan_items = len(await crud.get_pending_content_plan(ws)) if crawl_done else 0
        return {"workspace_id": workspace_id, "crawl_completed": crawl_done, "pending_plan_items": plan_items}

    @app.post("/api/agents/run")
    async def run_single_agent_endpoint(payload: RunAgentBody, user_id: CurrentUserId):
        from app.services.single_agent import AgentRunError, CrawlRequiredError, run_single_agent

        ws = uuid.UUID(payload.workspace_id)
        row = await db.fetch_one("SELECT user_id FROM workspaces WHERE id = $1", ws)
        if not row or row["user_id"] != user_id:
            raise HTTPException(404, "Workspace not found")
        agent = payload.agent.strip()
        try:
            out = await run_single_agent(str(ws), agent)
        except CrawlRequiredError:
            raise HTTPException(
                status_code=400,
                detail="Crawl must finish before running agents. Open the crawl step or POST /api/crawl and wait.",
            )
        except AgentRunError as e:
            raise HTTPException(status_code=400, detail=e.detail or e.code)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return out

    @app.post("/api/content-cycle/trigger")
    async def trigger_cycle(payload: TriggerCycleBody, user_id: CurrentUserId):
        ws = uuid.UUID(payload.workspace_id)
        row = await db.fetch_one("SELECT user_id FROM workspaces WHERE id = $1", ws)
        if not row or row["user_id"] != user_id:
            raise HTTPException(404, "Workspace not found")
        if not await crud.has_completed_crawl(ws):
            raise HTTPException(
                status_code=400,
                detail="Complete a site crawl before running the full content cycle.",
            )
        _queue_cycle(str(ws))
        return {"task_id": "queued", "workspace_id": str(ws)}

    @app.get("/api/content-cycle/{cycle_id}/status")
    async def cycle_status(cycle_id: str, user_id: CurrentUserId):
        row = await db.fetch_one(
            """
            SELECT c.* FROM content_cycles c
            JOIN workspaces w ON w.id = c.workspace_id
            WHERE c.id = $1::uuid AND w.user_id = $2
            """,
            cycle_id,
            user_id,
        )
        if not row:
            raise HTTPException(404, "Cycle not found")
        return dict(row)

    @app.get("/api/content/{workspace_id}")
    async def list_content(
        workspace_id: str,
        user_id: CurrentUserId,
        status: Optional[str] = None,
        agent: Optional[str] = None,
        content_type: Optional[str] = None,
    ):
        ws = uuid.UUID(workspace_id)
        row = await db.fetch_one("SELECT user_id FROM workspaces WHERE id = $1", ws)
        if not row or row["user_id"] != user_id:
            raise HTTPException(404, "Workspace not found")
        q = "SELECT * FROM content_drafts WHERE workspace_id = $1"
        args: list[Any] = [ws]
        i = 2
        if status:
            q += f" AND status = ${i}"
            args.append(status)
            i += 1
        if agent:
            q += f" AND agent_name = ${i}"
            args.append(agent)
            i += 1
        if content_type:
            q += f" AND content_type = ${i}"
            args.append(content_type)
            i += 1
        q += " ORDER BY created_at DESC LIMIT 200"
        rows = await db.fetch_all(q, *args)
        return {"items": [dict(r) for r in rows]}

    @app.patch("/api/content/{content_id}/approve")
    async def approve_content(content_id: str, user_id: CurrentUserId):
        row = await db.fetch_one(
            """
            SELECT d.id, d.workspace_id, d.body FROM content_drafts d
            JOIN workspaces w ON w.id = d.workspace_id
            WHERE d.id = $1::uuid AND w.user_id = $2
            """,
            content_id,
            user_id,
        )
        if not row:
            raise HTTPException(404, "Draft not found")
        body = str(row.get("body") or "")
        if body.lstrip().startswith("[quota-fallback]"):
            raise HTTPException(409, "Cannot approve quota fallback draft. Retry generation when Gemini quota is available.")
        await db.execute("UPDATE content_drafts SET status = 'approved' WHERE id = $1::uuid", content_id)
        asyncio.create_task(_resume_publish(uuid.UUID(row["workspace_id"]), content_id))
        return {"ok": True}

    @app.patch("/api/content/{content_id}/reject")
    async def reject_content(content_id: str, user_id: CurrentUserId):
        row = await db.fetch_one(
            """
            SELECT d.id FROM content_drafts d
            JOIN workspaces w ON w.id = d.workspace_id
            WHERE d.id = $1::uuid AND w.user_id = $2
            """,
            content_id,
            user_id,
        )
        if not row:
            raise HTTPException(404, "Draft not found")
        await db.execute("UPDATE content_drafts SET status = 'rejected' WHERE id = $1::uuid", content_id)
        return {"ok": True}

    @app.get("/api/keywords/{workspace_id}")
    async def keywords(workspace_id: str, user_id: CurrentUserId):
        await _assert_workspace(user_id, workspace_id)
        rows = await db.fetch_all(
            """
            SELECT keyword, position, previous_position, search_volume, checked_at
            FROM keyword_rankings WHERE workspace_id = $1 ORDER BY checked_at DESC LIMIT 500
            """,
            uuid.UUID(workspace_id),
        )
        if not rows:
            await _seed_demo_keywords(uuid.UUID(workspace_id))
            rows = await db.fetch_all(
                """
                SELECT keyword, position, previous_position, search_volume, checked_at
                FROM keyword_rankings WHERE workspace_id = $1 ORDER BY checked_at DESC LIMIT 500
                """,
                uuid.UUID(workspace_id),
            )
        return {"items": [dict(r) for r in rows]}

    @app.get("/api/backlinks/{workspace_id}")
    async def backlinks(workspace_id: str, user_id: CurrentUserId):
        await _assert_workspace(user_id, workspace_id)
        rows = await db.fetch_all(
            "SELECT * FROM backlinks WHERE workspace_id = $1 ORDER BY discovered_at DESC LIMIT 300",
            uuid.UUID(workspace_id),
        )
        if not rows:
            await _seed_demo_backlinks(uuid.UUID(workspace_id))
            rows = await db.fetch_all(
                "SELECT * FROM backlinks WHERE workspace_id = $1 ORDER BY discovered_at DESC LIMIT 300",
                uuid.UUID(workspace_id),
            )
        return {"items": [dict(r) for r in rows], "total": len(rows)}

    @app.get("/api/geo/{workspace_id}")
    async def geo(workspace_id: str, user_id: CurrentUserId):
        await _assert_workspace(user_id, workspace_id)
        rows = await db.fetch_all(
            "SELECT * FROM geo_mentions WHERE workspace_id = $1 ORDER BY detected_at DESC LIMIT 100",
            uuid.UUID(workspace_id),
        )
        return {"items": [dict(r) for r in rows]}

    @app.get("/api/analytics/{workspace_id}")
    async def analytics(workspace_id: str, user_id: CurrentUserId):
        await _assert_workspace(user_id, workspace_id)
        logs = await db.fetch_one(
            "SELECT COUNT(*) AS c FROM agent_logs WHERE workspace_id = $1",
            uuid.UUID(workspace_id),
        )
        drafts = await db.fetch_one(
            "SELECT COUNT(*) AS c FROM content_drafts WHERE workspace_id = $1",
            uuid.UUID(workspace_id),
        )
        pub = await db.fetch_one(
            "SELECT COUNT(*) AS c FROM content_drafts WHERE workspace_id = $1 AND status = 'published'",
            uuid.UUID(workspace_id),
        )
        score = await _weekly_seo_score(uuid.UUID(workspace_id))
        return {
            "agent_actions": int(logs["c"] if logs else 0),
            "drafts_total": int(drafts["c"] if drafts else 0),
            "published_total": int(pub["c"] if pub else 0),
            "weekly_seo_score": score,
        }

    @app.get("/api/activity/{workspace_id}")
    async def activity(
        workspace_id: str,
        user_id: CurrentUserId,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        await _assert_workspace(user_id, workspace_id)
        offset = (page - 1) * page_size
        rows = await db.fetch_all(
            """
            SELECT * FROM agent_logs WHERE workspace_id = $1
            ORDER BY created_at DESC LIMIT $2 OFFSET $3
            """,
            uuid.UUID(workspace_id),
            page_size,
            offset,
        )
        return {"items": [dict(r) for r in rows], "page": page, "page_size": page_size}

    @app.get("/api/agents/stream/{workspace_id}")
    async def agents_stream(workspace_id: str, user_id: CurrentUserId):
        ws = uuid.UUID(workspace_id)
        row = await db.fetch_one("SELECT user_id FROM workspaces WHERE id = $1", ws)
        if not row or row["user_id"] != user_id:
            raise HTTPException(404, "Workspace not found")

        async def gen() -> AsyncIterator[bytes]:
            q = await broker.subscribe(ws)
            try:
                yield b"retry: 5000\n\n"
                while True:
                    try:
                        msg = await asyncio.wait_for(q.get(), timeout=25.0)
                        yield msg.encode("utf-8")
                    except asyncio.TimeoutError:
                        yield b": keepalive\n\n"
            finally:
                await broker.unsubscribe(ws, q)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/api/competitors/{workspace_id}")
    async def competitors_panel(workspace_id: str, user_id: CurrentUserId):
        await _assert_workspace(user_id, workspace_id)
        prof = await db.fetch_one(
            "SELECT competitors, keywords FROM brand_profiles WHERE workspace_id = $1 ORDER BY version DESC LIMIT 1",
            uuid.UUID(workspace_id),
        )
        comps = list(prof["competitors"]) if prof and prof["competitors"] else []
        kws = list(prof["keywords"]) if prof and prof["keywords"] else []
        overlap = [{"competitor": c, "shared_keywords": kws[:5], "gap_topics": ["comparison guides", "pricing transparency", "case studies"]} for c in comps[:3]]
        return {"items": overlap}

    @app.post("/api/stripe/webhook")
    async def stripe_webhook(request: Request):
        s = get_settings()
        if not s.stripe_secret_key:
            raise HTTPException(501, "Stripe not configured")
        import stripe

        stripe.api_key = s.stripe_secret_key
        payload = await request.body()
        sig = request.headers.get("stripe-signature", "")
        if not s.stripe_webhook_secret:
            raise HTTPException(501, "Stripe webhook secret not configured")
        try:
            event = stripe.Webhook.construct_event(payload, sig, s.stripe_webhook_secret)
        except Exception as e:
            raise HTTPException(400, str(e)) from e
        if event["type"] == "customer.subscription.updated":
            # Map price to plan tier in production
            pass
        return {"received": True}

    @app.get("/health")
    async def health():
        return {"ok": True}

    return app


async def _assert_workspace(user_id: uuid.UUID, workspace_id: str) -> None:
    row = await db.fetch_one(
        "SELECT id FROM workspaces WHERE id = $1::uuid AND user_id = $2",
        workspace_id,
        user_id,
    )
    if not row:
        raise HTTPException(404, "Workspace not found")


async def _seed_demo_keywords(ws: uuid.UUID) -> None:
    seeds = [
        ("brand visibility", 12, 14, 1900),
        ("generative engine optimization", 8, 10, 720),
        ("ai search optimization", 15, None, 480),
    ]
    for kw, pos, prev, vol in seeds:
        await db.execute(
            """
            INSERT INTO keyword_rankings (workspace_id, keyword, position, previous_position, search_volume)
            VALUES ($1,$2,$3,$4,$5)
            """,
            ws,
            kw,
            pos,
            prev,
            vol,
        )


async def _seed_demo_backlinks(ws: uuid.UUID) -> None:
    await db.execute(
        """
        INSERT INTO backlinks (workspace_id, source_url, target_url, domain_authority)
        VALUES ($1,'https://example.com/ref','https://client.example',42)
        """,
        ws,
    )


async def _weekly_seo_score(ws: uuid.UUID) -> dict:
    kcount = await db.fetch_one("SELECT COUNT(*) c FROM keyword_rankings WHERE workspace_id = $1", ws)
    bcount = await db.fetch_one("SELECT COUNT(*) c FROM backlinks WHERE workspace_id = $1", ws)
    gcount = await db.fetch_one("SELECT COUNT(*) c FROM geo_mentions WHERE workspace_id = $1", ws)
    dcount = await db.fetch_one("SELECT COUNT(*) c FROM content_drafts WHERE workspace_id = $1 AND status='published'", ws)
    technical = 72
    content = min(95, 40 + int(dcount["c"] if dcount else 0) * 3)
    bl = min(90, 30 + int(bcount["c"] if bcount else 0) * 5)
    geo = min(85, 20 + int(gcount["c"] if gcount else 0) * 10)
    kw = min(90, 35 + int(kcount["c"] if kcount else 0) * 2)
    total = int((technical + content + bl + geo + kw) / 5)
    return {
        "total": total,
        "breakdown": {
            "technical_seo": technical,
            "content_volume": content,
            "backlinks": bl,
            "geo_mentions": geo,
            "keyword_movements": kw,
        },
    }


async def _resume_publish(ws: uuid.UUID, content_id: str) -> None:
    from app.services.publishers import dispatch_publication

    row = await db.fetch_one("SELECT * FROM content_drafts WHERE id = $1::uuid AND workspace_id = $2", content_id, ws)
    if not row:
        return
    d = dict(row)
    draft = {
        "id": str(d["id"]),
        "agent_name": d["agent_name"],
        "content_type": d["content_type"],
        "title": d["title"],
        "body": d["body"],
        "platform": d["platform"],
    }
    ok, detail = await dispatch_publication(ws, draft)
    await db.execute(
        """
        UPDATE content_drafts SET status = $1, published_at = CASE WHEN $2 THEN now() ELSE published_at END
        WHERE id = $3::uuid
        """,
        "published" if ok else "failed",
        ok,
        content_id,
    )
    await broker.publish(
        ws,
        {"type": "publish", "content_id": content_id, "ok": ok, "detail": detail, "at": datetime.now(timezone.utc).isoformat()},
    )


app = create_app()
