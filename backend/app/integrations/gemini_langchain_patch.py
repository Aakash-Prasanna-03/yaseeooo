"""Patch LangChain Google chat retries so 429 does not immediately retry.

langchain_google_genai.chat_models wires Tenacity to retry ResourceExhausted; on
free tier that burns 2× quota for one logical call. We only retry true
transients (e.g. 503).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

import google.api_core.exceptions
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_log = logging.getLogger(__name__)


def _create_retry_decorator_patched() -> Callable[[Any], Any]:
    return retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=2, min=1, max=60),
        retry=retry_if_exception_type(google.api_core.exceptions.ServiceUnavailable),
        before_sleep=before_sleep_log(logging.getLogger("tenacity"), logging.WARNING),
    )


def apply() -> None:
    import langchain_google_genai.chat_models as cm

    cm._create_retry_decorator = _create_retry_decorator_patched  # type: ignore[assignment]
    _log.debug("gemini_langchain_patch: 429 (ResourceExhausted) will not be retried by LangChain")
