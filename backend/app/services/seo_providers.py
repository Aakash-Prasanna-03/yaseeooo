"""DataForSEO + Reddit signals (mock when credentials absent)."""
from __future__ import annotations

import base64
from typing import Any, Dict, List

import httpx

from app.config import get_settings


async def fetch_keyword_ideas(workspace_id: str, seed_keywords: List[str]) -> List[Dict[str, Any]]:
    s = get_settings()
    if not s.dataforseo_login or not s.dataforseo_password:
        return [
            {"keyword": k, "volume": 1200, "difficulty": 40, "score": 0.7 - i * 0.05}
            for i, k in enumerate(seed_keywords or ["brand growth", "content marketing"])
        ]
    auth = base64.b64encode(f"{s.dataforseo_login}:{s.dataforseo_password}".encode()).decode()
    out: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=60) as client:
        for kw in seed_keywords[:5]:
            r = await client.post(
                "https://api.dataforseo.com/v3/keywords_data/google_ads/keywords_for_keywords/live",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                json=[{"keywords": [kw], "location_code": 2840, "language_code": "en"}],
            )
            if r.status_code != 200:
                continue
            data = r.json()
            for task in data.get("tasks", []) or []:
                for item in (task.get("result") or [{}])[0].get("items", []) or []:
                    out.append(
                        {
                            "keyword": item.get("keyword"),
                            "volume": item.get("search_volume"),
                            "difficulty": item.get("keyword_difficulty"),
                            "score": float(item.get("search_volume") or 0) / 10000.0,
                        }
                    )
    return out or [{"keyword": "demo", "volume": 500, "difficulty": 30, "score": 0.5}]


def reddit_trending_mock(industry: str) -> List[Dict[str, Any]]:
    return [
        {"source": "reddit", "topic": f"{industry} tips", "score": 0.55},
        {"source": "reddit", "topic": f"best tools for {industry}", "score": 0.52},
    ]
