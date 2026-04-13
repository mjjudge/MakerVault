"""Abstract base class and data types for all AI provider adapters.

Every adapter must subclass :class:`AIProvider` and implement at minimum
:meth:`complete` and :meth:`health_check`.  Embeddings are optional — adapters
that do not support them should raise ``NotImplementedError``.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from makervault.models.ai_provider_config import AIProviderConfig


# ---------------------------------------------------------------------------
# Shared data types
# ---------------------------------------------------------------------------


@dataclass
class ChatMessage:
    """A single turn in a conversation sent to / received from an AI model."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class CompletionOptions:
    """Optional knobs that callers can pass when requesting a completion."""

    temperature: float = 0.7
    max_tokens: int | None = None
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class AIProvider(ABC):
    """Abstract base class for all AI provider adapters.

    Subclasses must implement :meth:`complete` and :meth:`health_check`.
    Embeddings are optional.

    API keys are **never** passed in directly.  Instead, the ``config`` record
    stores the *name* of the environment variable that holds the key; the
    adapter resolves it at instantiation time via :meth:`_resolve_api_key`.
    """

    def __init__(self, config: "AIProviderConfig") -> None:
        self.config = config
        self._api_key: str | None = self._resolve_api_key()

    # ------------------------------------------------------------------
    # Interface — must be implemented by every adapter
    # ------------------------------------------------------------------

    @abstractmethod
    async def complete(
        self,
        messages: list[ChatMessage],
        options: CompletionOptions | None = None,
    ) -> str:
        """Send a list of chat messages and return the assistant's reply text."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable and responding correctly."""

    # ------------------------------------------------------------------
    # Interface — optional; raise NotImplementedError if unsupported
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        """Return an embedding vector for *text*.

        Raises ``NotImplementedError`` if the provider does not support
        embeddings.  Callers should check :attr:`supports_embeddings` before
        calling this method.
        """
        raise NotImplementedError(
            f"Provider '{self.config.name}' does not support embeddings."
        )

    @property
    def supports_embeddings(self) -> bool:
        """Whether this adapter implements :meth:`embed`."""
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_api_key(self) -> str | None:
        """Look up the API key from the environment variable named in config.

        Returns ``None`` if no ``api_key_env_var`` is set (e.g. local Ollama
        with no authentication).  Raises ``EnvironmentError`` if the env var
        is set in config but absent from the environment.
        """
        env_var = self.config.api_key_env_var
        if not env_var:
            return None
        value = os.environ.get(env_var)
        if value is None:
            raise EnvironmentError(
                f"AI provider '{self.config.name}' requires environment variable "
                f"'{env_var}' which is not set."
            )
        return value

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<{self.__class__.__name__} name={self.config.name!r} "
            f"type={self.config.provider_type!r} model={self.config.model!r}>"
        )
