"""Run one agent at a time; requires a completed crawl. Uses brand_profiles + embeddings + pending_content_plan."""
from __future__ import annotations


class CrawlRequiredError(Exception):
    pass


class AgentRunError(Exception):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(detail or code)

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app import crud
from app import database as db
from app.agents import prompts
from app.agents.runner import run_agent, tier_for_sam
from app.graph.pipeline import (
    _write_one,
    node_brand_context,
    node_content_planning,
    node_start,
    node_trend_analysis,
)
from app.graph.state import DraftItem, GraphState
from app.sse_broker import broker

RUNNABLE = frozenset({"Maya", "Sam", "Zoe", "Leo", "Aria", "Finn", "Nova"})

_DEFAULT_ITEM: Dict[str, Dict[str, Any]] = {
    "Sam": {
        "title": "Pillar SEO article",
        "content_type": "blog",
        "platform": "wordpress",
        "agent": "Sam",
        "rationale": "Authority",
    },
    "Zoe": {
        "title": "LinkedIn thought leadership",
        "content_type": "linkedin",
        "platform": "linkedin",
        "agent": "Zoe",
        "rationale": "Awareness",
    },
    "Leo": {
        "title": "Reddit helpful answer",
        "content_type": "reddit",
        "platform": "reddit",
        "agent": "Leo",
        "rationale": "Community",
    },
    "Aria": {
        "title": "GEO FAQ block",
        "content_type": "geo",
        "platform": "site",
        "agent": "Aria",
        "rationale": "GEO",
    },
}


async def _build_context_state(workspace_id: str) -> GraphState:
    base: GraphState = {
        "workspace_id": workspace_id,
        "brand_profile": {},
        "memory_snippets": [],
        "trends": [],
        "content_plan": [],
        "drafts": [],
        "errors": [],
    }
    s1 = await node_start(base)
    s2 = await node_brand_context({**base, **s1})
    s3 = await node_trend_analysis({**base, **s1, **s2})
    return {**base, **s1, **s2, **s3}


async def _persist_draft(ws: uuid.UUID, d: DraftItem) -> DraftItem:
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
        {
            "type": "agent_log",
            "agent": d["agent_name"],
            "action": "draft_created",
            "platform": d.get("platform"),
            "at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {**d, "id": did}


def _pick_plan_item(plan: List[dict], agent_name: str) -> dict:
    for item in plan:
        if str(item.get("agent", "")).lower() == agent_name.lower():
            return item
    if plan:
        return plan[0]
    return dict(_DEFAULT_ITEM[agent_name])


async def run_single_agent(workspace_id: str, agent_name: str) -> dict:
    if agent_name not in RUNNABLE:
        raise ValueError(f"Unknown agent: {agent_name}")
    ws = uuid.UUID(workspace_id)
    if not await crud.has_completed_crawl(ws):
        raise CrawlRequiredError()

    state = await _build_context_state(workspace_id)

    if agent_name == "Maya":
        st = await node_content_planning(state)
        plan = st.get("content_plan") or []
        await crud.set_pending_content_plan(ws, plan)
        await db.execute(
            """
            INSERT INTO agent_logs (workspace_id, agent_name, action_type, platform, token_count, outcome_metric)
            VALUES ($1,'Maya','content_plan','all',0,$2::jsonb)
            """,
            ws,
            json.dumps({"items": len(plan)}),
        )
        await broker.publish(
            ws,
            {
                "type": "agent_log",
                "agent": "Maya",
                "action": "content_plan",
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"agent": "Maya", "content_plan": plan, "plan_items_saved": len(plan)}

    if agent_name in ("Sam", "Zoe", "Leo"):
        plan = await crud.get_pending_content_plan(ws)
        item = _pick_plan_item(plan, agent_name)
        draft = await _write_one(item, state)
        saved = await _persist_draft(ws, draft)
        return {"agent": agent_name, "draft_id": saved["id"], "title": saved.get("title")}

    if agent_name == "Aria":
        row = await db.fetch_one(
            """
            SELECT id::text, body, title, platform, agent_name
            FROM content_drafts
            WHERE workspace_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            ws,
        )
        if not row:
            raise AgentRunError("no_draft", "Create a draft with Sam, Zoe, or Leo before running Aria.")
        bp = state.get("brand_profile") or {}
        ctx = prompts.brand_context_block(bp)
        user = (
            f"{ctx}\nAdd FAQ JSON-LD + Q&A blocks + entity-rich summary to this draft:\n"
            f"{str(row.get('body') or '')[:6000]}"
        )
        text, tok = await run_agent("Aria", prompts.ARIA, user, "pro")
        new_body = str(row["body"] or "") + "\n\n--- GEO Layer ---\n" + text
        await db.execute(
            "UPDATE content_drafts SET body = $1 WHERE id = $2::uuid",
            new_body,
            row["id"],
        )
        await db.execute(
            """
            INSERT INTO agent_logs (workspace_id, agent_name, action_type, platform, content_id, token_count, outcome_metric)
            VALUES ($1,'Aria','geo_optimize',$2,$3::uuid,$4,$5::jsonb)
            """,
            ws,
            row.get("platform"),
            row["id"],
            tok,
            json.dumps({}),
        )
        await broker.publish(
            ws,
            {
                "type": "agent_log",
                "agent": "Aria",
                "action": "geo_optimize",
                "content_id": row["id"],
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"agent": "Aria", "draft_id": row["id"], "geo_applied": True}

    if agent_name == "Finn":
        bp = state.get("brand_profile") or {}
        ctx = prompts.brand_context_block(bp)
        user = f"{ctx}\nTask: Draft one concise outreach email (subject line + body) for a relevant partnership or guest post opportunity."
        text, tok = await run_agent("Finn", prompts.FINN, user, "flash")
        draft: DraftItem = {
            "id": str(uuid.uuid4()),
            "agent_name": "Finn",
            "content_type": "email",
            "title": "Outreach draft",
            "body": text,
            "platform": "email",
            "status": "pending",
            "_tokens": tok,
        }
        saved = await _persist_draft(ws, draft)
        return {"agent": "Finn", "draft_id": saved["id"]}

    if agent_name == "Nova":
        bp = state.get("brand_profile") or {}
        ctx = prompts.brand_context_block(bp)
        rows = await db.fetch_all(
            """
            SELECT id::text, agent_name, platform, status, title
            FROM content_drafts
            WHERE workspace_id = $1
            ORDER BY created_at DESC
            LIMIT 25
            """,
            ws,
        )
        summary_payload = [dict(r) for r in rows]
        user = f"{ctx}\nCycle drafts summary: {json.dumps(summary_payload, default=str)}"
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
        await broker.publish(
            ws,
            {
                "type": "agent_log",
                "agent": "Nova",
                "action": "monitoring",
                "at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"agent": "Nova", "summary": text[:8000], "tokens": tok}

    raise ValueError(agent_name)
