"""Structured brand profile via Gemini (LangChain). Falls back to heuristics without API key or on API errors."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.config import get_settings

_log = logging.getLogger(__name__)


def _fallback_profile(
    merged_crawl: Dict[str, Any],
    business_name: str,
    business_description: str,
    onboarding_competitors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    agg = merged_crawl.get("aggregate", {})
    colors = agg.get("colors") or {"primary": "#4f46e5", "secondary": "#6366f1", "accent": "#f97316"}
    keywords = agg.get("keyword_seeds") or []
    competitors = list(dict.fromkeys((onboarding_competitors or []) + agg.get("competitor_hints", [])))[:15]
    tone = "Professional and clear, based on homepage copy."
    body = " ".join(agg.get("body_excerpts", []))[:2000]
    if body:
        tone = f"Derived from site copy: {body[:400]}..."
    return {
        "colors": colors,
        "typography": agg.get("typography_hint") or "System fonts / see site stylesheet",
        "tone_of_voice": tone,
        "keywords": keywords[:25],
        "competitors": competitors,
        "social_handles": agg.get("social_links") or {},
        "industry": "General business (inferred heuristically)",
        "cta_language": ", ".join(agg.get("cta_candidates", [])[:5]) or "Learn more, Get started",
        "content_structure": "Blog paths: " + ", ".join(agg.get("blog_paths", [])[:5]),
    }


async def structure_brand_profile(
    merged_crawl: Dict[str, Any],
    business_name: str,
    business_description: str,
    onboarding_competitors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    s = get_settings()
    if not s.google_api_key:
        return _fallback_profile(merged_crawl, business_name, business_description, onboarding_competitors)

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ChatGoogleGenerativeAI(
        model=s.gemini_pro,
        google_api_key=s.google_api_key,
        temperature=0.2,
    )
    schema_hint = """Return a single JSON object with keys:
    colors: {primary, secondary, accent} hex strings,
    typography: string summary,
    tone_of_voice: string,
    keywords: string array (max 25),
    competitors: string array (urls or names),
    social_handles: object string->url,
    industry: string,
    cta_language: string summary of CTA phrasing,
    content_structure: string summary of blog/content IA
    """
    payload = json.dumps(merged_crawl, default=str)[:28000]
    msg = [
        SystemMessage(
            content="You are a brand strategist. Infer accurate fields from crawl + business context. No markdown."
        ),
        HumanMessage(
            content=f"Business: {business_name}\nAbout: {business_description}\n"
            f"Onboarding competitors: {onboarding_competitors or []}\nCrawl JSON:\n{payload}\n\n{schema_hint}"
        ),
    ]
    try:
        resp = await llm.ainvoke(msg)
    except Exception as e:
        cur: BaseException | None = e
        while cur is not None:
            name = type(cur).__name__
            msg_l = str(cur).lower()
            if "ResourceExhausted" in name or "you exceeded your current quota" in msg_l or (
                "429" in str(cur) and "quota" in msg_l
            ):
                return _fallback_profile(merged_crawl, business_name, business_description, onboarding_competitors)
            cur = cur.__cause__
        raise
    text = getattr(resp, "content", str(resp))
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
        if not isinstance(data, dict):
            raise ValueError("not dict")
        return data
    except Exception:
        return _fallback_profile(merged_crawl, business_name, business_description, onboarding_competitors)
