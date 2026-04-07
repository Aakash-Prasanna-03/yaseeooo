"""
Brand Intelligence Crawl: Playwright + BeautifulSoup.
Target: complete under 60s — uses short timeout and single main page + light link follow.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
except ImportError:  # pragma: no cover
    async_playwright = None  # type: ignore
    PlaywrightTimeout = Exception  # type: ignore


@dataclass
class CrawlResult:
    url: str
    html_pages: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


def _same_domain(base: str, link: str) -> bool:
    try:
        return urlparse(base).netloc == urlparse(link).netloc
    except Exception:
        return False


def extract_colors_from_css_and_inline(html: str) -> Dict[str, str]:
    """Heuristic: find hex colors in style blocks and inline styles."""
    hexes = re.findall(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b", html)
    uniq: List[str] = []
    for h in hexes:
        full = f"#{h}" if len(h) in (3, 6) else h
        if full not in uniq:
            uniq.append(full.lower() if full.startswith("#") else f"#{h.lower()}")
    primary = uniq[0] if uniq else "#4f46e5"
    secondary = uniq[1] if len(uniq) > 1 else "#6366f1"
    accent = uniq[2] if len(uniq) > 2 else "#f97316"
    return {"primary": primary, "secondary": secondary, "accent": accent}


def parse_page(url: str, html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string or "").strip() if soup.title else ""
    metas = {m.get("name") or m.get("property") or "": m.get("content", "") for m in soup.find_all("meta") if m.get("content")}
    headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"])][:40]
    body_text = " ".join(soup.get_text(separator=" ", strip=True).split())[:12000]
    buttons = [b.get_text(strip=True) for b in soup.find_all(["button", "a"], class_=re.compile(r"btn|cta|button", re.I))][:30]
    links = [a.get("href") for a in soup.find_all("a", href=True)]
    internal = []
    social = {}
    competitor_mentions: List[str] = []
    for href in links:
        if not href:
            continue
        low = href.lower()
        if any(s in low for s in ("twitter.com", "x.com", "linkedin.com", "facebook.com", "instagram.com", "github.com")):
            for key in ("twitter", "linkedin", "facebook", "instagram", "github"):
                if key in low:
                    social[key] = href
        if "vs" in low or "compare" in low or "alternative" in low:
            competitor_mentions.append(href)
    colors = extract_colors_from_css_and_inline(html)
    font_link = soup.find("link", href=re.compile(r"fonts.googleapis.com", re.I))
    typography = font_link.get("href", "") if font_link else ""
    blog_hints = [a.get("href") for a in soup.find_all("a", href=True) if a.get("href") and re.search(r"blog|article|news", a.get("href", ""), re.I)]
    keywords_meta = metas.get("keywords", "") or metas.get("Keywords", "")
    kw_list = [k.strip() for k in re.split(r"[,;]", keywords_meta) if k.strip()]
    if not kw_list:
        kw_list = [h for h in headings if len(h) < 60][:15]
    return {
        "title": title,
        "meta": metas,
        "headings": headings,
        "body_excerpt": body_text[:4000],
        "cta_candidates": list({t for t in buttons if t})[:20],
        "social_links": social,
        "competitor_hints": competitor_mentions[:20],
        "colors": colors,
        "typography_hint": typography,
        "keyword_seeds": kw_list[:30],
        "blog_paths": list({urljoin(url, p) for p in blog_hints if p})[:10],
    }


async def crawl_brand_site(url: str, max_seconds: int = 55) -> CrawlResult:
    result = CrawlResult(url=url)
    if not url.startswith("http"):
        url = "https://" + url
    if async_playwright is None:
        result.errors.append("playwright_not_installed")
        return result

    stop_at = asyncio.get_event_loop().time() + max_seconds

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            except PlaywrightTimeout:
                result.errors.append("main_timeout")
            html = await page.content()
            result.html_pages[url] = html
            soup = BeautifulSoup(html, "html.parser")
            to_visit: Set[str] = set()
            for a in soup.find_all("a", href=True)[:80]:
                if asyncio.get_event_loop().time() > stop_at:
                    break
                full = urljoin(url, a["href"])
                if _same_domain(url, full) and full not in result.html_pages:
                    if any(x in full.lower() for x in ("blog", "about", "pricing", "product")):
                        to_visit.add(full.split("#")[0])
            for link in list(to_visit)[:4]:
                if asyncio.get_event_loop().time() > stop_at:
                    break
                try:
                    await page.goto(link, wait_until="domcontentloaded", timeout=15000)
                    result.html_pages[link] = await page.content()
                except Exception as e:
                    result.errors.append(f"subpage:{link}:{e}")
        finally:
            await browser.close()
    return result


def merge_crawl_parse(crawl: CrawlResult) -> Dict[str, Any]:
    merged: Dict[str, Any] = {
        "pages": {},
        "aggregate": {
            "colors": {},
            "headings": [],
            "keyword_seeds": [],
            "cta_candidates": [],
            "social_links": {},
            "competitor_hints": [],
            "blog_paths": [],
            "body_excerpts": [],
        },
    }
    for u, html in crawl.html_pages.items():
        p = parse_page(u, html)
        merged["pages"][u] = p
        agg = merged["aggregate"]
        agg["colors"] = p.get("colors") or agg["colors"]
        agg["headings"].extend(p.get("headings", []))
        agg["keyword_seeds"].extend(p.get("keyword_seeds", []))
        agg["cta_candidates"].extend(p.get("cta_candidates", []))
        agg["social_links"].update(p.get("social_links", {}))
        agg["competitor_hints"].extend(p.get("competitor_hints", []))
        agg["blog_paths"].extend(p.get("blog_paths", []))
        agg["body_excerpts"].append(p.get("body_excerpt", ""))
    # dedupe
    agg = merged["aggregate"]
    agg["headings"] = list(dict.fromkeys(agg["headings"]))[:50]
    agg["keyword_seeds"] = list(dict.fromkeys(agg["keyword_seeds"]))[:40]
    agg["cta_candidates"] = list(dict.fromkeys(agg["cta_candidates"]))[:25]
    agg["competitor_hints"] = list(dict.fromkeys(agg["competitor_hints"]))[:25]
    agg["blog_paths"] = list(dict.fromkeys(agg["blog_paths"]))[:15]
    return merged
