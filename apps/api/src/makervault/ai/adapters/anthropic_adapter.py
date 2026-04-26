"""Anthropic Claude adapter.

Calls the Anthropic Messages API (``/v1/messages``).
The API key is read from the environment variable named in
``config.api_key_env_var`` (typically ``ANTHROPIC_API_KEY``).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import httpx

from makervault.ai.base import AIProvider, ChatMessage, CompletionOptions

if TYPE_CHECKING:
    from makervault.models.ai_provider_config import AIProviderConfig

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://api.anthropic.com"
_API_VERSION = "2023-06-01"


class AnthropicProvider(AIProvider):
    """Adapter for Anthropic Claude models."""

    def __init__(self, config: "AIProviderConfig") -> None:
        super().__init__(config)
        self._base_url = (config.base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._headers = {
            "Content-Type": "application/json",
            "anthropic-version": _API_VERSION,
        }
        if self._api_key:
            self._headers["x-api-key"] = self._api_key

    async def complete(
        self,
        messages: list[ChatMessage],
        options: CompletionOptions | None = None,
    ) -> str:
        opts = options or CompletionOptions()

        # Anthropic separates the system prompt from the message list.
        system_content: str | None = None
        user_messages: list[dict] = []
        for m in messages:
            if m.role == "system":
                system_content = m.content
            else:
                user_messages.append({"role": m.role, "content": m.content})

        payload: dict = {
            "model": self.config.model,
            "messages": user_messages,
            "temperature": opts.temperature,
            "max_tokens": opts.max_tokens or 1024,
        }
        if system_content:
            payload["system"] = system_content
        payload.update(opts.extra)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/v1/messages",
                headers=self._headers,
                content=json.dumps(payload),
            )
            response.raise_for_status()
            data = response.json()

        try:
            return data["content"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise ValueError(f"Unexpected response format from Anthropic: {data}") from exc

    async def health_check(self) -> bool:
        """Verify the Anthropic endpoint is reachable with a minimal request."""
        try:
            payload = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self._base_url}/v1/messages",
                    headers=self._headers,
                    content=json.dumps(payload),
                )
                return response.status_code == 200
        except Exception as exc:
            logger.warning(
                "Anthropic health check failed for '%s': %s", self.config.name, exc
            )
            return False
