"""AI provider service — configuration loading and provider selection.

This module is the bridge between the database (``AIProviderConfig`` rows) and
the concrete adapter instances (:class:`~makervault.ai.base.AIProvider`).

Functions
---------
get_active_provider
    Return an instantiated adapter for the current default enabled provider,
    or ``None`` if none is configured.
get_provider_by_id
    Return an instantiated adapter for a specific provider config record.
build_provider
    Construct the correct adapter for a given ``AIProviderConfig`` row.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.models.ai_provider_config import AIProviderConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_provider(config: AIProviderConfig):
    """Instantiate the correct adapter for *config*.

    Returns an :class:`~makervault.ai.base.AIProvider` instance.
    Raises ``ValueError`` for unknown provider types.
    Raises ``EnvironmentError`` if a required API key env var is missing.
    """
    from makervault.ai.adapters.ollama_adapter import OllamaProvider
    from makervault.ai.adapters.openai_adapter import OpenAIProvider

    match config.provider_type:
        case "openai" | "openai_compatible":
            return OpenAIProvider(config)
        case "ollama":
            return OllamaProvider(config)
        case _:
            raise ValueError(
                f"Unknown AI provider type: '{config.provider_type}'. "
                f"Supported types: openai, openai_compatible, ollama."
            )


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


async def get_active_provider(db: AsyncSession):
    """Return an adapter for the default enabled provider, or ``None``.

    Prefers the row where ``is_default=True`` and ``is_enabled=True``.
    Falls back to the first enabled provider if no default is set.
    """
    result = await db.execute(
        select(AIProviderConfig)
        .where(AIProviderConfig.is_enabled.is_(True))
        .order_by(
            AIProviderConfig.is_default.desc(),
            AIProviderConfig.created_at.asc(),
        )
        .limit(1)
    )
    config = result.scalar_one_or_none()
    if config is None:
        return None
    try:
        return build_provider(config)
    except (ValueError, EnvironmentError) as exc:
        logger.warning("Could not instantiate default AI provider: %s", exc)
        return None


async def get_provider_by_id(db: AsyncSession, provider_id):
    """Return an adapter for a specific provider config ID, or ``None``."""
    config = await db.get(AIProviderConfig, provider_id)
    if config is None:
        return None
    return build_provider(config)
