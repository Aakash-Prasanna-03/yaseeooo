"""LangChain tool: crawl URL → merged parse JSON string."""
from __future__ import annotations

import json

from langchain_core.tools import tool

from app.services.crawler import crawl_brand_site, merge_crawl_parse


@tool
async def brand_intelligence_crawl(url: str) -> str:
    """Fetch and parse a brand website (Playwright + BeautifulSoup). Returns merged JSON."""
    result = await crawl_brand_site(url)
    merged = merge_crawl_parse(result)
    return json.dumps({"merged": merged, "errors": result.errors}, default=str)
