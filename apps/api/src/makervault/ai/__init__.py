"""AI provider abstraction package.

This package defines the common interfaces that every AI provider adapter must
implement, plus the concrete adapters and the service that wires them together.

Usage (from a FastAPI route)::

    from makervault.ai.service import get_active_provider
    from makervault.config import get_settings
    from makervault.database import get_db_session

    provider = await get_active_provider(db, get_settings())
    if provider:
        reply = await provider.complete([ChatMessage(role="user", content="Hello")])
"""

from makervault.ai.base import AIProvider, ChatMessage
from makervault.ai.service import get_active_provider, get_provider_by_id

__all__ = [
    "AIProvider",
    "ChatMessage",
    "get_active_provider",
    "get_provider_by_id",
]
