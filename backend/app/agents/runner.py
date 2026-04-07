"""Invoke LLM via LangChain with conditional model tier."""
from __future__ import annotations

import logging
from typing import Any, Literal, Optional

import google.api_core.exceptions
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import get_settings
from app.agents import prompts


Tier = Literal["pro", "flash"]
_log = logging.getLogger(__name__)


def _local_quota_fallback(agent_name: str, user_prompt: str) -> str:
    brief = user_prompt.replace("\n", " ").strip()
    brief = brief[:900] if len(brief) > 900 else brief
    return (
        f"[quota-fallback] {agent_name} draft (local fallback)\n\n"
        "Gemini free-tier quota is temporarily unavailable, so this is a locally generated scaffold.\n\n"
        "Working brief:\n"
        f"{brief}\n\n"
        "Suggested draft structure:\n"
        "1) Strong headline and one-line promise\n"
        "2) Problem context and why it matters now\n"
        "3) Core solution with 3 practical steps\n"
        "4) Short proof point / example\n"
        "5) CTA tailored to platform and audience\n\n"
        "Next step: retry this agent when Gemini quota resets to replace this scaffold with full AI copy."
    )


def get_llm(tier: Tier) -> Optional[Any]:
    s = get_settings()
    provider = (s.llm_provider or "gemini").lower()
    if provider == "openai":
        if not s.openai_api_key:
            return None
        from langchain_openai import ChatOpenAI

        model = s.openai_pro_model if tier == "pro" else s.openai_flash_model
        return ChatOpenAI(model=model, api_key=s.openai_api_key, temperature=0.35)
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        model = s.ollama_pro_model if tier == "pro" else s.ollama_flash_model
        return ChatOllama(model=model, temperature=0.35, base_url=s.ollama_base_url)

    if not s.google_api_key:
        return None
    model = s.gemini_pro if tier == "pro" else s.gemini_flash
    return ChatGoogleGenerativeAI(model=model, google_api_key=s.google_api_key, temperature=0.35)


async def run_agent(
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    tier: Tier,
) -> tuple[str, int]:
    s = get_settings()
    provider = (s.llm_provider or "gemini").lower()
    llm = get_llm(tier)
    if llm is None:
        body = f"[offline-mock] {agent_name} ({provider}) would process: {user_prompt[:200]}..."
        return body, 0
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    try:
        resp = await llm.ainvoke(messages)
    except google.api_core.exceptions.ResourceExhausted as exc:
        # Free-tier quota exhaustion should not crash the request path.
        _log.warning("Gemini quota exhausted for agent=%s tier=%s: %s", agent_name, tier, exc)
        body = _local_quota_fallback(agent_name, user_prompt)
        return body, 0
    except Exception:
        if provider in {"openai", "ollama"}:
            _log.warning("%s request failed for agent=%s tier=%s", provider, agent_name, tier, exc_info=True)
            hint = "OPENAI_API_KEY/model" if provider == "openai" else "OLLAMA_BASE_URL/model and local Ollama service"
            body = f"[provider-error] {agent_name} could not run on {provider}. Check {hint}."
            return body, 0
        raise
    text = getattr(resp, "content", str(resp))
    usage = getattr(resp, "usage_metadata", None) or {}
    tokens = int(usage.get("total_tokens") or usage.get("total_token_count") or 0)
    return text, tokens


def tier_for_sam(word_target: int) -> Tier:
    return "pro" if word_target >= 800 else "flash"


def tier_for_finn(task: str) -> Tier:
    return "pro" if "guest" in task.lower() or "pitch" in task.lower() else "flash"
