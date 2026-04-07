"""
LangGraph 10-node content pipeline (supervisor flow).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal

from langgraph.graph import END, StateGraph

from app import crud
from app import database as db
from app.agents import prompts
from app.agents.runner import run_agent, tier_for_sam
from app.config import get_settings
from app.graph.state import DraftItem, GraphState
from app.services import embeddings as emb_svc
from app.services.seo_providers import fetch_keyword_ideas, reddit_trending_mock
from app.sse_broker import broker


async def node_start(state: GraphState) -> GraphState:
    ws = uuid.UUID(state["workspace_id"])
    snippets = await emb_svc.search_brand_memory(ws, "brand voice keywords offerings", top_k=8)
    return {**state, "memory_snippets": snippets, "errors": state.get("errors", [])}


async def node_brand_context(state: GraphState) -> GraphState:
    row = await db.fetch_one(
        """
        SELECT * FROM brand_profiles
        WHERE workspace_id = $1
        ORDER BY version DESC, crawled_at DESC NULLS LAST
        LIMIT 1
        """,
        uuid.UUID(state["workspace_id"]),
    )
    profile = dict(row) if row else {}
    if profile:
        bp = {
            "colors": profile.get("colors") or {},
            "typography": profile.get("typography"),
            "tone_of_voice": profile.get("tone_of_voice"),
            "keywords": profile.get("keywords") or [],
            "competitors": profile.get("competitors") or [],
            "social_handles": profile.get("social_handles") or {},
            "industry": profile.get("industry"),
            "cta_language": profile.get("cta_language"),
            "content_structure": profile.get("content_structure"),
        }
    else:
        bp = state.get("brand_profile") or {}
    return {**state, "brand_profile": bp}


async def node_trend_analysis(state: GraphState) -> GraphState:
    ws = state["workspace_id"]
    kws = state.get("brand_profile", {}).get("keywords") or ["seo", "marketing"]
    ideas = await fetch_keyword_ideas(ws, kws[:5])
    reddit = reddit_trending_mock(state.get("brand_profile", {}).get("industry", "business"))
    trends = [*ideas, *reddit]
    trends.sort(key=lambda x: -float(x.get("score", 0)))
    return {**state, "trends": trends[:12]}


async def node_content_planning(state: GraphState) -> GraphState:
    ctx = prompts.brand_context_block(state.get("brand_profile", {}))
    trend_blob = json.dumps(state.get("trends", [])[:8], default=str)
    sys = prompts.MAYA
    user = f"{ctx}\nTrends:\n{trend_blob}\nReturn JSON array of 3-5 objects with keys: title, content_type, platform, agent (Sam|Zoe|Leo|Aria), rationale."
    text, _ = await run_agent("Maya", sys, user, "pro")
    plan: List[Dict[str, Any]] = []
    try:
        start = text.index("[")
        end = text.rindex("]") + 1
        plan = json.loads(text[start:end])
    except Exception:
        plan = [
            {"title": "Pillar SEO article", "content_type": "blog", "platform": "wordpress", "agent": "Sam", "rationale": "Authority"},
            {"title": "LinkedIn thought leadership", "content_type": "linkedin", "platform": "linkedin", "agent": "Zoe", "rationale": "Awareness"},
            {"title": "Reddit helpful answer", "content_type": "reddit", "platform": "reddit", "agent": "Leo", "rationale": "Community"},
            {"title": "GEO FAQ block", "content_type": "geo", "platform": "site", "agent": "Aria", "rationale": "GEO"},
        ]
    return {**state, "content_plan": plan}


async def _write_one(item: Dict[str, Any], state: GraphState) -> DraftItem:
    bp = state.get("brand_profile", {})
    ctx = prompts.brand_context_block(bp)
    agent = item.get("agent", "Sam")
    title = item.get("title", "Untitled")
    platform = item.get("platform", "web")
    ctype = item.get("content_type", "blog")
    user = f"{ctx}\nTask: produce draft for:\n{json.dumps(item, default=str)}"
    if agent == "Sam":
        text, tok = await run_agent("Sam", prompts.SAM, user + "\nTarget 700-1000 words.", tier_for_sam(900))
    elif agent == "Zoe":
        text, tok = await run_agent("Zoe", prompts.ZOE, user, "flash")
    elif agent == "Leo":
        text, tok = await run_agent("Leo", prompts.LEO, user, "flash")
    else:
        text, tok = await run_agent("Aria", prompts.ARIA, user, "pro")
    draft: DraftItem = {
        "id": str(uuid.uuid4()),
        "agent_name": agent,
        "content_type": ctype if ctype in ("blog", "linkedin", "reddit", "twitter", "quora", "geo", "email") else "blog",
        "title": title,
        "body": text,
        "platform": platform,
        "status": "pending",
        "_tokens": tok,
    }
    return draft


async def node_writers_parallel(state: GraphState) -> GraphState:
    items = state.get("content_plan", [])[:5]
    drafts = await asyncio.gather(*[_write_one(i, state) for i in items])
    ws = uuid.UUID(state["workspace_id"])
    saved: List[DraftItem] = []
    for d in drafts:
        h = hashlib.sha256(d["body"].encode()).hexdigest()
        row = await db.fetch_one(
            """
            INSERT INTO content_drafts (id, workspace_id, agent_name, content_type, title, body, platform, status, content_hash)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            RETURNING id::text
            """,
            uuid.UUID(d["id"]),
            ws,
            d["agent_name"],
            d["content_type"],
            d.get("title"),
            d["body"],
            d.get("platform"),
            d.get("status", "pending"),
            h,
        )
        did = row["id"] if row else d["id"]
        await db.execute(
            """
            INSERT INTO agent_logs (workspace_id, agent_name, action_type, platform, content_id, token_count, outcome_metric)
            VALUES ($1,$2,$3,$4,$5::uuid,$6,$7::jsonb)
            """,
            ws,
            d["agent_name"],
            "draft_created",
            d.get("platform"),
            did,
            int(d.get("_tokens") or 0),
            json.dumps({"chars": len(d["body"])}),
        )
        await broker.publish(
            ws,
            {"type": "agent_log", "agent": d["agent_name"], "action": "draft_created", "platform": d.get("platform"), "at": datetime.now(timezone.utc).isoformat()},
        )
        saved.append({**d, "id": did})
    return {**state, "drafts": saved}


def route_after_review(state: GraphState) -> Literal["geo", "wait"]:
    if state.get("awaiting_approval"):
        return "wait"
    return "geo"


async def node_review(state: GraphState) -> GraphState:
    ws = uuid.UUID(state["workspace_id"])
    row = await db.fetch_one("SELECT approval_mode FROM workspaces WHERE id = $1", ws)
    approval = bool(row and row["approval_mode"])
    if not approval:
        return {**state, "awaiting_approval": False}
    for d in state.get("drafts", []):
        await db.execute(
            "UPDATE content_drafts SET status = 'awaiting_approval' WHERE id = $1::uuid",
            d["id"],
        )
        await broker.publish(
            ws,
            {"type": "draft_queued", "content_id": d["id"], "agent": d["agent_name"], "at": datetime.now(timezone.utc).isoformat()},
        )
    return {**state, "awaiting_approval": True}


async def node_geo(state: GraphState) -> GraphState:
    bp = state.get("brand_profile", {})
    ctx = prompts.brand_context_block(bp)
    enriched: List[DraftItem] = []
    for d in state.get("drafts", []):
        user = f"{ctx}\nAdd FAQ JSON-LD + Q&A blocks + entity-rich summary to this draft:\n{d.get('body','')[:6000]}"
        text, tok = await run_agent("Aria", prompts.ARIA, user, "pro")
        new_body = d["body"] + "\n\n--- GEO Layer ---\n" + text
        await db.execute(
            "UPDATE content_drafts SET body = $1 WHERE id = $2::uuid",
            new_body,
            d["id"],
        )
        await db.execute(
            """
            INSERT INTO agent_logs (workspace_id, agent_name, action_type, platform, content_id, token_count, outcome_metric)
            VALUES ($1,'Aria','geo_optimize',$2,$3::uuid,$4,$5::jsonb)
            """,
            uuid.UUID(state["workspace_id"]),
            d.get("platform"),
            d["id"],
            tok,
            json.dumps({}),
        )
        enriched.append({**d, "body": new_body})
    return {**state, "drafts": enriched}


async def node_publish(state: GraphState) -> GraphState:
    from app.services.publishers import dispatch_publication

    ws = uuid.UUID(state["workspace_id"])
    for d in state.get("drafts", []):
        ok, detail = await dispatch_publication(ws, d)
        status = "published" if ok else "failed"
        await db.execute(
            """
            UPDATE content_drafts SET status = $1, published_at = CASE WHEN $2 THEN now() ELSE NULL END
            WHERE id = $3::uuid
            """,
            status,
            ok,
            d["id"],
        )
        await db.execute(
            """
            INSERT INTO agent_logs (workspace_id, agent_name, action_type, platform, content_id, token_count, outcome_metric)
            VALUES ($1,'Finn','publish',$2,$3::uuid,0,$4::jsonb)
            """,
            ws,
            d.get("platform"),
            d["id"],
            json.dumps({"ok": ok, "detail": detail}),
        )
        await broker.publish(
            ws,
            {"type": "publish", "content_id": d["id"], "ok": ok, "detail": detail, "at": datetime.now(timezone.utc).isoformat()},
        )
    return {**state}


async def node_monitoring(state: GraphState) -> GraphState:
    s = get_settings()
    ws = uuid.UUID(state["workspace_id"])
    from app.services.geo_monitor import detect_geo_mentions

    await detect_geo_mentions(ws, state.get("brand_profile", {}))
    # Nova summary
    ctx = prompts.brand_context_block(state.get("brand_profile", {}))
    user = f"{ctx}\nCycle drafts summary: {json.dumps([{k: d.get(k) for k in ('id','agent_name','platform','status')} for d in state.get('drafts',[])], default=str)}"
    text, tok = await run_agent("Nova", prompts.NOVA, user, "flash")
    await db.execute(
        """
        INSERT INTO agent_logs (workspace_id, agent_name, action_type, platform, token_count, outcome_metric)
        VALUES ($1,'Nova','monitoring','all',$2,$3::jsonb)
        """,
        ws,
        tok,
        json.dumps({"summary": text[:4000]}),
    )
    if s.geo_monitoring_mock:
        await db.execute(
            """
            INSERT INTO geo_mentions (workspace_id, engine, query_used, mention_snippet, confidence_score)
            VALUES ($1,'perplexity',$2,$3,0.42)
            """,
            ws,
            f"{state.get('brand_profile',{}).get('industry','brand')} overview",
            "Demo GEO mention — set GEO_MONITORING_MOCK=false and configure monitors for live checks.",
        )
    return {**state}


async def node_feedback(state: GraphState) -> GraphState:
    summary = {
        "drafts": len(state.get("drafts", [])),
        "trends_used": len(state.get("trends", [])),
        "memory_snippets": len(state.get("memory_snippets", [])),
    }
    return {**state, "summary": summary}


def build_graph():
    g = StateGraph(GraphState)
    g.add_node("startup", node_start)
    g.add_node("brand_context", node_brand_context)
    g.add_node("trend_analysis", node_trend_analysis)
    g.add_node("content_planning", node_content_planning)
    g.add_node("writers_parallel", node_writers_parallel)
    g.add_node("review_gate", node_review)
    g.add_node("geo_layer", node_geo)
    g.add_node("publication", node_publish)
    g.add_node("monitoring", node_monitoring)
    g.add_node("feedback_loop", node_feedback)

    g.set_entry_point("startup")
    g.add_edge("startup", "brand_context")
    g.add_edge("brand_context", "trend_analysis")
    g.add_edge("trend_analysis", "content_planning")
    g.add_edge("content_planning", "writers_parallel")
    g.add_edge("writers_parallel", "review_gate")
    g.add_conditional_edges(
        "review_gate",
        route_after_review,
        {"geo": "geo_layer", "wait": "feedback_loop"},
    )
    g.add_edge("geo_layer", "publication")
    g.add_edge("publication", "monitoring")
    g.add_edge("monitoring", "feedback_loop")
    g.add_edge("feedback_loop", END)
    return g.compile()


compiled_graph = build_graph()


async def run_content_cycle(workspace_id: str, cycle_id: str | None = None) -> GraphState:
    ws_uuid = uuid.UUID(workspace_id)
    if not await crud.has_completed_crawl(ws_uuid):
        raise RuntimeError("crawl_required_before_full_cycle")
    if cycle_id:
        cid = cycle_id
        await db.execute(
            """
            INSERT INTO content_cycles (id, workspace_id, status, summary)
            VALUES ($1::uuid, $2, 'running', '{}'::jsonb)
            """,
            cid,
            ws_uuid,
        )
    else:
        row = await db.fetch_one(
            """
            INSERT INTO content_cycles (workspace_id, status, summary)
            VALUES ($1, 'running', '{}'::jsonb)
            RETURNING id::text
            """,
            ws_uuid,
        )
        cid = row["id"] if row else str(uuid.uuid4())
    init: GraphState = {
        "workspace_id": workspace_id,
        "brand_profile": {},
        "memory_snippets": [],
        "trends": [],
        "content_plan": [],
        "drafts": [],
        "cycle_id": cid,
        "approval_mode": True,
        "awaiting_approval": False,
        "summary": {},
        "errors": [],
    }
    try:
        out = await compiled_graph.ainvoke(init)
        pieces = len(out.get("drafts", []))
        await db.execute(
            """
            UPDATE content_cycles SET completed_at = now(), status = 'completed', pieces_generated = $1, pieces_published = $2, summary = $3::jsonb
            WHERE id = $4::uuid
            """,
            pieces,
            pieces if not out.get("awaiting_approval") else 0,
            json.dumps(out.get("summary", {})),
            cid,
        )
        return out
    except Exception as e:
        await db.execute(
            "UPDATE content_cycles SET completed_at = now(), status = 'failed', summary = $1::jsonb WHERE id = $2::uuid",
            json.dumps({"error": str(e)}),
            cid,
        )
        raise
