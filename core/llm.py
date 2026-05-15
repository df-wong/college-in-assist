"""Thin wrapper around the OpenAI Chat Completions API with retry."""
from __future__ import annotations
 
import logging
from typing import Iterable

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)


class LLM:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> str:
        """Send a single-turn chat and return the assistant message text."""
        log.debug("LLM call model=%s tokens<=%s", self._model, max_tokens)
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()

    def chat_messages(
        self,
        messages: Iterable[dict],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> str:
        """Multi-turn variant when caller already has a message list."""
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=list(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
