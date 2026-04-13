"""Ollama adapter.

Calls a locally-running Ollama instance via its REST API
(``/api/chat`` for completions, ``/api/embeddings`` for vectors).
Ollama does not require an API key by default; ``config.api_key_env_var``
should be left ``None`` unless the instance has been secured.

Default base URL: ``http://ollama:11434`` (matches the Docker Compose service
name in this project's ``docker-compose.yml``).
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

_DEFAULT_BASE_URL = "http://ollama:11434"


class OllamaProvider(AIProvider):
    """Adapter for a self-hosted Ollama instance.

    Uses the Ollama REST API which is *not* OpenAI-compatible at the path
    level (it uses ``/api/chat`` and ``/api/embeddings``), though the shape
    of the message list is similar to OpenAI's.
    """

    def __init__(self, config: "AIProviderConfig") -> None:
        super().__init__(config)
        self._base_url = (config.base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
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
            "stream": False,
            "options": {"temperature": opts.temperature},
        }
        if opts.max_tokens is not None:
            payload["options"]["num_predict"] = opts.max_tokens

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                headers=self._headers,
                content=json.dumps(payload),
            )
            response.raise_for_status()
            data = response.json()

        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Unexpected response format from Ollama: {data}") from exc

    async def health_check(self) -> bool:
        """Verify Ollama is running by hitting the version endpoint."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/api/version")
                return response.status_code == 200
        except Exception as exc:
            logger.warning("Ollama health check failed for '%s': %s", self.config.name, exc)
            return False

    async def embed(self, text: str) -> list[float]:
        payload = {"model": self.config.model, "prompt": text}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self._base_url}/api/embeddings",
                headers=self._headers,
                content=json.dumps(payload),
            )
            response.raise_for_status()
            data = response.json()
        try:
            return data["embedding"]
        except KeyError as exc:
            raise ValueError(f"Unexpected embedding response format from Ollama: {data}") from exc

    @property
    def supports_embeddings(self) -> bool:
        return True
