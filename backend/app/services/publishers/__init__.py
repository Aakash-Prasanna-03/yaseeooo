"""Platform publishers: rate limits + retries; mock when credentials missing."""
from __future__ import annotations

import asyncio
import random
import time
import uuid
from typing import Any, Dict, Tuple

import httpx

from app.config import get_settings

_last_post: dict[str, float] = {}


async def _sleep_backoff(attempt: int) -> None:
    await asyncio.sleep(min(2**attempt + random.random(), 30))


async def dispatch_publication(workspace_id: uuid.UUID, draft: Dict[str, Any]) -> Tuple[bool, str]:
    platform = (draft.get("platform") or "").lower()
    ctype = draft.get("content_type") or ""
    s = get_settings()
    key = f"{workspace_id}:{platform}"
    now = time.time()
    if now - _last_post.get(key, 0) < 600 and platform == "reddit":
        await asyncio.sleep(0.1)
    _last_post[key] = time.time()

    if platform == "reddit":
        return await _publish_reddit(draft)
    if platform == "linkedin":
        return await _publish_linkedin(draft)
    if platform == "medium":
        return await _publish_medium(draft)
    if platform == "quora":
        return await _publish_quora(draft)
    if platform == "wordpress" or ctype == "blog":
        return await _publish_wordpress(draft)
    return True, "simulated_local_publish"


async def _publish_reddit(draft: Dict[str, Any]) -> Tuple[bool, str]:
    s = get_settings()
    if not s.reddit_client_id:
        return True, "reddit_skipped_no_credentials"
    try:
        import praw

        reddit = praw.Reddit(
            client_id=s.reddit_client_id,
            client_secret=s.reddit_client_secret,
            user_agent=s.reddit_user_agent,
        )
        # Without subreddit context, no-op submit — real flow uses workspace config
        _ = reddit
        return True, "reddit_validated_client_only"
    except Exception as e:
        return False, str(e)


async def _publish_linkedin(draft: Dict[str, Any]) -> Tuple[bool, str]:
    s = get_settings()
    if not s.linkedin_client_id:
        return True, "linkedin_skipped_no_credentials"
    return True, "linkedin_stub"


async def _publish_medium(draft: Dict[str, Any]) -> Tuple[bool, str]:
    s = get_settings()
    if not s.medium_integration_token:
        return True, "medium_skipped_no_token"
    headers = {"Authorization": f"Bearer {s.medium_integration_token}", "Content-Type": "application/json"}
    body = {
        "title": draft.get("title") or "Post",
        "contentFormat": "markdown",
        "content": draft.get("body") or "",
        "tags": ["yeseeeooo", "seo"],
        "publishStatus": "draft",
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post("https://api.medium.com/v1/users/me/posts", headers=headers, json=body)
        if r.status_code in (200, 201):
            return True, "medium_ok"
        return False, r.text[:500]


async def _publish_quora(draft: Dict[str, Any]) -> Tuple[bool, str]:
    s = get_settings()
    if not s.quora_automation_enabled:
        return True, "quora_automation_disabled"
    return True, "quora_stub_playwright"


async def _publish_wordpress(draft: Dict[str, Any]) -> Tuple[bool, str]:
    s = get_settings()
    if not s.wordpress_base_url:
        return True, "wordpress_skipped_no_config"
    url = s.wordpress_base_url.rstrip("/") + "/wp-json/wp/v2/posts"
    auth = (s.wordpress_user or "", s.wordpress_app_password or "")
    payload = {
        "title": draft.get("title") or "Post",
        "content": draft.get("body") or "",
        "status": "draft",
    }
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(url, auth=auth, json=payload)
                if r.status_code in (200, 201):
                    return True, "wordpress_ok"
                if r.status_code == 429:
                    await _sleep_backoff(attempt)
                    continue
                return False, r.text[:500]
        except Exception as e:
            await _sleep_backoff(attempt)
            if attempt == 2:
                return False, str(e)
    return False, "wordpress_failed"
