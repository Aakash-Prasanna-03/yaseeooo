"""Workspace and content helpers."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from asyncpg.exceptions import ForeignKeyViolationError, UndefinedColumnError

from app import database as db


async def upsert_user(user_id: uuid.UUID, email: Optional[str]) -> None:
    stmt = """
        INSERT INTO users (id, email) VALUES ($1, $2)
        ON CONFLICT (id) DO UPDATE SET email = COALESCE(EXCLUDED.email, users.email)
        """
    try:
        await db.execute(stmt, user_id, email)
    except ForeignKeyViolationError:
        # Local dev schema can keep users.id -> auth.users.id without auth bootstrapping.
        # Seed a minimal auth row and retry app-level user upsert.
        await db.execute(
            "INSERT INTO auth.users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
            user_id,
        )
        await db.execute(stmt, user_id, email)


async def get_default_workspace(user_id: uuid.UUID) -> Optional[dict]:
    return await db.fetch_one(
        "SELECT * FROM workspaces WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
        user_id,
    )


async def create_workspace(
    user_id: uuid.UUID,
    business_name: str,
    business_description: str,
    website_url: str,
    target_audience: str,
    primary_goal: str,
    platforms: List[str],
    competitors: Optional[List[str]] = None,
) -> uuid.UUID:
    trial_end = datetime.now(timezone.utc) + timedelta(days=14)
    row = await db.fetch_one(
        """
        INSERT INTO workspaces (user_id, business_name, business_description, website_url, target_audience, primary_goal, platforms, trial_ends_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7::text[],$8)
        RETURNING id
        """,
        user_id,
        business_name,
        business_description,
        website_url,
        target_audience,
        primary_goal,
        platforms,
        trial_end,
    )
    wid = row["id"]
    if competitors:
        await db.execute(
            """
            INSERT INTO brand_profiles (workspace_id, competitors, crawled_at)
            VALUES ($1, $2::text[], NULL)
            """,
            wid,
            competitors,
        )
    return wid


async def save_brand_profile(workspace_id: uuid.UUID, profile: dict, raw_crawl: dict) -> None:
    vrow = await db.fetch_one(
        "SELECT COALESCE(MAX(version), 0) + 1 AS v FROM brand_profiles WHERE workspace_id = $1",
        workspace_id,
    )
    ver = int(vrow["v"]) if vrow else 1
    await db.execute(
        """
        INSERT INTO brand_profiles (
          workspace_id, colors, typography, tone_of_voice, keywords, competitors,
          social_handles, industry, cta_language, content_structure, raw_crawl_data, crawled_at, version
        ) VALUES (
          $1, $2::jsonb, $3, $4, $5::text[], $6::text[], $7::jsonb, $8, $9, $10, $11::jsonb, now(), $12
        )
        """,
        workspace_id,
        json.dumps(profile.get("colors") or {}),
        profile.get("typography"),
        profile.get("tone_of_voice"),
        profile.get("keywords") or [],
        profile.get("competitors") or [],
        json.dumps(profile.get("social_handles") or {}),
        profile.get("industry"),
        profile.get("cta_language"),
        profile.get("content_structure"),
        json.dumps(raw_crawl),
        ver,
    )


async def has_completed_crawl(workspace_id: uuid.UUID) -> bool:
    """True once a crawl has persisted a brand_profiles row with crawled_at set."""
    row = await db.fetch_one(
        """
        SELECT 1 AS ok FROM brand_profiles
        WHERE workspace_id = $1 AND crawled_at IS NOT NULL
        ORDER BY version DESC
        LIMIT 1
        """,
        workspace_id,
    )
    return row is not None


async def get_pending_content_plan(workspace_id: uuid.UUID) -> List[dict]:
    try:
        row = await db.fetch_one(
            "SELECT pending_content_plan FROM workspaces WHERE id = $1",
            workspace_id,
        )
    except UndefinedColumnError:
        return []
    if not row:
        return []
    p = row["pending_content_plan"]
    if p is None:
        return []
    if isinstance(p, str):
        return json.loads(p)
    return list(p)


async def set_pending_content_plan(workspace_id: uuid.UUID, plan: List[dict]) -> None:
    try:
        await db.execute(
            "UPDATE workspaces SET pending_content_plan = $2::jsonb WHERE id = $1",
            workspace_id,
            json.dumps(plan),
        )
    except UndefinedColumnError:
        # Run supabase/migrations/20260407120000_workspace_pending_plan.sql (or equivalent ALTER).
        pass
