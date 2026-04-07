"""Stripe Phase 5: usage limits per plan tier."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app import database as db

LIMITS = {
    "free": 999999,
    "starter": 20,
    "growth": 100,
    "agency": 999999,
}


async def get_period_usage(user_id: uuid.UUID) -> tuple[int, str]:
    row = await db.fetch_one("SELECT plan_tier FROM users WHERE id = $1", user_id)
    tier = (row["plan_tier"] if row else "free") or "free"
    today = dt.date.today()
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1)
    else:
        end = start.replace(month=start.month + 1, day=1)
    urow = await db.fetch_one(
        """
        SELECT pieces_used FROM billing_usage
        WHERE user_id = $1 AND period_start = $2
        """,
        user_id,
        start,
    )
    used = int(urow["pieces_used"]) if urow else 0
    return used, tier


class BillingLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        s = get_settings()
        if not s.stripe_secret_key:
            return await call_next(request)
        if request.url.path not in {"/api/content-cycle/trigger", "/api/onboard"}:
            return await call_next(request)
        uid = request.headers.get("X-User-Plan-Check")
        if not uid:
            return await call_next(request)
        try:
            user_uuid = uuid.UUID(uid)
        except ValueError:
            return await call_next(request)
        used, tier = await get_period_usage(user_uuid)
        if used >= LIMITS.get(tier, 20):
            return Response("Usage limit exceeded for billing period", status_code=402)
        return await call_next(request)
