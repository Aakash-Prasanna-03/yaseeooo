"""GEO mention detection hooks (mock-friendly)."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from app import database as db


async def detect_geo_mentions(workspace_id: uuid.UUID, brand_profile: Dict[str, Any]) -> None:
    # Placeholder for live ChatGPT/Perplexity/SGE automation
    _ = brand_profile
    return
