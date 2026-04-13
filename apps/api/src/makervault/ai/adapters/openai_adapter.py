"""OpenAI adapter.

Calls the OpenAI Chat Completions API (``/v1/chat/completions``).
The API key is read from the environment variable named in
``config.api_key_env_var`` (typically ``OPENAI_API_KEY``).

This adapter also supports any OpenAI-compatible endpoint when
``config.provider_type == "openai_compatible"`` and ``config.base_url`` is
set to a custom base URL (e.g. a self-hosted vLLM instance).
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

_DEFAULT_BASE_URL = "https://api.openai.com"


class OpenAIProvider(AIProvider):
    """Adapter for OpenAI and OpenAI-compatible endpoints.

    Covers:
    - ``provider_type = "openai"``  → hosted OpenAI (default base URL)
    - ``provider_type = "openai_compatible"`` → any custom base URL
    """

    def __init__(self, config: "AIProviderConfig") -> None:
        super().__init__(config)
        self._base_url = (config.base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._headers = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            self._headers["Authorization"] = f"Bearer {self._api_key}"

    # ------------------------------------------------------------------
    # AIProvider interface
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[ChatMessage],
        options: CompletionOptions | None = None,
    ) -> str:
        opts = options or CompletionOptions()
        payload: dict = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": opts.temperature,
        }
        if opts.max_tokens is not None:
            payload["max_tokens"] = opts.max_tokens
        payload.update(opts.extra)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers=self._headers,
                content=json.dumps(payload),
            )
            response.raise_for_status()
            data = response.json()

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise ValueError(f"Unexpected response format from OpenAI: {data}") from exc

    async def health_check(self) -> bool:
        """Verify the endpoint is reachable by listing available models."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self._base_url}/v1/models",
                    headers=self._headers,
                )
                return response.status_code == 200
        except Exception as exc:
            logger.warning("OpenAI health check failed for '%s': %s", self.config.name, exc)
            return False

    async def embed(self, text: str) -> list[float]:
        payload = {"model": self.config.model, "input": text}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/v1/embeddings",
                headers=self._headers,
                content=json.dumps(payload),
            )
            response.raise_for_status()
            data = response.json()
        try:
            return data["data"][0]["embedding"]
        except (KeyError, IndexError) as exc:
            raise ValueError(f"Unexpected embedding response format: {data}") from exc

    @property
    def supports_embeddings(self) -> bool:
        return True
