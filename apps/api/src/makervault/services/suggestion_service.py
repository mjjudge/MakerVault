"""AI project suggestion service.

This module builds inventory-grounded prompts for the "what can I build?"
workflow and parses the AI response.

All AI calls go through the provider abstraction layer
(:mod:`makervault.ai.service`) — no provider is hard-coded here.

Response schema
---------------
The AI is asked to return JSON with this shape::

    {
      "suggestions": [
        {
          "title": "LED Matrix Clock",
          "description": "Build a clock using your ESP32...",
          "difficulty": "beginner|intermediate|advanced",
          "owned_parts": [
            {"part_id": "uuid-string", "part_name": "ESP32 DevKit V1"}
          ],
          "missing_parts": [
            {"name": "MAX7219 LED Matrix", "notes": "inexpensive, ~$3"}
          ]
        }
      ]
    }
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

if TYPE_CHECKING:
    from makervault.ai.base import AIProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = (
    "You are MakerVault, a helpful assistant for electronics and workshop "
    "inventory management.  The user wants project inspiration grounded in "
    "their actual inventory.  Always respond with valid JSON only — no markdown "
    "fences, no extra explanation."
)

_MAX_PARTS = 80  # Cap the number of parts included in the context


def _build_inventory_context(parts_with_stock: list[dict]) -> str:
    """Build a plain-text inventory context string from a list of part dicts.

    Each dict must contain at minimum ``id``, ``name``, and ``total_stock``.
    Optional fields: ``part_kind``, ``short_description``, ``tags``,
    ``manufacturer``, ``part_code``.
    """
    if not parts_with_stock:
        return "The inventory is currently empty.\n"

    lines = ["Current inventory (parts with available stock):\n"]
    for p in parts_with_stock:
        name = p.get("name", "?")
        part_id = p.get("id", "")
        qty = p.get("total_stock", 0)
        kind = p.get("part_kind") or ""
        desc = p.get("short_description") or ""
        tags = p.get("tags") or []
        manufacturer = p.get("manufacturer") or ""

        tag_str = ", ".join(tags[:5]) if tags else ""
        meta_parts = [x for x in [kind, manufacturer, desc] if x]
        meta_str = " — " + "; ".join(meta_parts) if meta_parts else ""

        line = f"  • [{part_id}] {name} (qty: {qty}){meta_str}"
        if tag_str:
            line += f" [tags: {tag_str}]"
        lines.append(line)

    return "\n".join(lines)


def _build_suggestion_messages(prompt: str, inventory_context: str) -> list[dict]:
    user_content = (
        f"{inventory_context}\n\n"
        f"User request: {prompt}\n\n"
        "Return JSON with this structure:\n"
        "  suggestions  (array of up to 3 project ideas, each with):\n"
        "    title         (string — short project name)\n"
        "    description   (string — 2-3 sentences)\n"
        "    difficulty    (string — 'beginner', 'intermediate', or 'advanced')\n"
        "    owned_parts   (array of {part_id, part_name} for parts in the inventory above)\n"
        "    missing_parts (array of {name, notes} for parts not in the inventory)\n"
        "\n"
        "Only reference part_id values that appear in the inventory list above.  "
        "If a part_id cannot be matched, omit it.  Be concise and practical."
    )
    return [
        {"role": "system", "content": _SYSTEM_INSTRUCTION},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# JSON extraction helper (shared with enrichment_service)
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from *text*, stripping any markdown fences."""
    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    return json.loads(stripped)


# ---------------------------------------------------------------------------
# Inventory context loader
# ---------------------------------------------------------------------------


async def load_inventory_context(db: AsyncSession) -> tuple[list[dict], str]:
    """Load parts that have available stock and build a context string.

    Returns ``(parts_data, context_string)`` where ``parts_data`` is a list
    of dicts (one per distinct part) and ``context_string`` is the formatted
    inventory text ready to embed in an AI prompt.
    """
    from makervault.models.part import Part
    from makervault.models.stock_item import StockItem

    # Subquery: sum available quantities per part
    from sqlalchemy import func

    qty_subq = (
        select(
            StockItem.part_id,
            func.sum(StockItem.quantity).label("total_stock"),
        )
        .where(StockItem.status == "available")
        .group_by(StockItem.part_id)
        .subquery()
    )

    result = await db.execute(
        select(Part, qty_subq.c.total_stock)
        .join(qty_subq, Part.id == qty_subq.c.part_id)
        .where(Part.is_active.is_(True))
        .order_by(Part.name)
        .limit(_MAX_PARTS)
    )
    rows = result.all()

    parts_data = []
    for part, total_stock in rows:
        parts_data.append(
            {
                "id": str(part.id),
                "name": part.name,
                "part_code": part.part_code,
                "part_kind": part.part_kind,
                "short_description": part.short_description,
                "manufacturer": part.manufacturer,
                "tags": list(part.tags) if part.tags else [],
                "total_stock": float(total_stock),
            }
        )

    context = _build_inventory_context(parts_data)
    return parts_data, context


# ---------------------------------------------------------------------------
# Main service function
# ---------------------------------------------------------------------------


async def run_suggestion(
    prompt: str,
    db: AsyncSession,
    provider: "AIProvider",
) -> dict[str, Any]:
    """Run the AI suggestion call for *prompt* using *provider*.

    Loads inventory context from *db*, builds grounded messages, calls the
    provider, and returns the parsed result dict.

    Raises any exception on failure — the caller is responsible for catching
    and storing ``error_message``.
    """
    from makervault.ai.base import ChatMessage, CompletionOptions

    _, inventory_context = await load_inventory_context(db)
    raw_messages = _build_suggestion_messages(prompt, inventory_context)
    messages = [ChatMessage(role=m["role"], content=m["content"]) for m in raw_messages]
    options = CompletionOptions(temperature=0.7, max_tokens=2048)

    response_text = await provider.complete(messages, options)
    result = _extract_json(response_text)

    # Normalise: ensure ``suggestions`` is a list
    if "suggestions" not in result or not isinstance(result["suggestions"], list):
        result = {"suggestions": []}

    return result
