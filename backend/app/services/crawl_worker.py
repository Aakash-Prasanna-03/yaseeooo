"""Async crawl job: Playwright → structured profile → DB + embeddings."""
from __future__ import annotations

import uuid

from app import crud
from app import database as db
from app.services import embeddings as emb
from app.services.brand_intel import structure_brand_profile
from app.services.crawler import crawl_brand_site, merge_crawl_parse


async def run_crawl(workspace_id: uuid.UUID) -> None:
    row = await db.fetch_one("SELECT website_url, business_name, business_description FROM workspaces WHERE id = $1", workspace_id)
    if not row or not row["website_url"]:
        return
    url = row["website_url"]
    biz = row["business_name"] or "Business"
    desc = row["business_description"] or ""
    comp_row = await db.fetch_one("SELECT competitors FROM brand_profiles WHERE workspace_id = $1 ORDER BY version DESC LIMIT 1", workspace_id)
    onboarding_competitors = list(comp_row["competitors"]) if comp_row and comp_row["competitors"] else []
    crawl = await crawl_brand_site(url)
    merged = merge_crawl_parse(crawl)
    profile = await structure_brand_profile(merged, biz, desc, onboarding_competitors)
    if onboarding_competitors and not profile.get("competitors"):
        profile["competitors"] = onboarding_competitors
    await crud.save_brand_profile(workspace_id, profile, {"crawl": merged, "errors": crawl.errors})
    texts = [
        f"{biz}: {desc}",
        profile.get("tone_of_voice") or "",
        " ".join(profile.get("keywords") or [])[:4000],
        merged.get("aggregate", {}).get("body_excerpts", [""])[0][:4000],
    ]
    await emb.upsert_brand_memory(workspace_id, [t for t in texts if t], {"workspace_id": str(workspace_id)})
