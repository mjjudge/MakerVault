"""AI enrichment service.

This module contains the prompt builders and result parsers for the four
enrichment job types.  All AI calls go through the provider abstraction layer
(:mod:`makervault.ai.service`) — no provider is hard-coded here.

Job types
---------
summarise_document
    Produce a plain-text summary of a document's extracted text plus any
    key specs and referenced part numbers.

extract_metadata
    Pull structured metadata fields (manufacturer, part number, package,
    capabilities, tags) from a document's extracted text.

generate_aliases
    Suggest alternate names and common aliases for a part so it can be found
    by different search terms.

classify_part
    Suggest the appropriate ``part_kind``, relevant tags, and a confidence
    score for a part given its name and description.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from makervault.ai.base import AIProvider
    from makervault.models.document import Document
    from makervault.models.part import Part

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = (
    "You are MakerVault, a helpful assistant for electronics and workshop "
    "inventory management.  Always respond with valid JSON only — no markdown "
    "fences, no extra explanation."
)


def _build_summarise_document_messages(doc: "Document") -> list[dict]:
    text_excerpt = (doc.text_extracted or "")[:6000]
    user_content = (
        f"Document title: {doc.title}\n"
        f"Document type: {doc.document_type}\n\n"
        f"Text:\n{text_excerpt}\n\n"
        "Return JSON with these fields:\n"
        "  summary       (string, ≤ 3 sentences)\n"
        "  key_specs     (list of short spec strings, e.g. '3.3 V supply')\n"
        "  part_numbers  (list of part number strings found in the text)\n"
    )
    return [
        {"role": "system", "content": _SYSTEM_INSTRUCTION},
        {"role": "user", "content": user_content},
    ]


def _build_extract_metadata_messages(doc: "Document") -> list[dict]:
    text_excerpt = (doc.text_extracted or "")[:6000]
    user_content = (
        f"Document title: {doc.title}\n"
        f"Document type: {doc.document_type}\n\n"
        f"Text:\n{text_excerpt}\n\n"
        "Return JSON with these fields:\n"
        "  manufacturer   (string or null)\n"
        "  part_number    (string or null)\n"
        "  package_type   (string or null, e.g. 'DIP-8', 'SOT-23')\n"
        "  capabilities   (object of key-value spec pairs, or {})\n"
        "  tags           (list of lowercase tag strings)\n"
        "  confidence     (integer 0-100)\n"
    )
    return [
        {"role": "system", "content": _SYSTEM_INSTRUCTION},
        {"role": "user", "content": user_content},
    ]


def _build_generate_aliases_messages(part: "Part") -> list[dict]:
    user_content = (
        f"Part name: {part.name}\n"
        f"Description: {part.short_description or 'N/A'}\n"
        f"Manufacturer: {part.manufacturer or 'N/A'}\n"
        f"Manufacturer part number: {part.manufacturer_part_number or 'N/A'}\n"
        f"Part kind: {part.part_kind or 'N/A'}\n\n"
        "Suggest alternate names, common abbreviations, and search aliases for "
        "this part.  Return JSON with these fields:\n"
        "  aliases     (list of strings — do not include the original name)\n"
        "  confidence  (integer 0-100)\n"
    )
    return [
        {"role": "system", "content": _SYSTEM_INSTRUCTION},
        {"role": "user", "content": user_content},
    ]


def _build_classify_part_messages(part: "Part") -> list[dict]:
    from makervault.models.part import PART_KIND_VALUES

    kinds_str = ", ".join(PART_KIND_VALUES)
    user_content = (
        f"Part name: {part.name}\n"
        f"Description: {part.short_description or 'N/A'}\n"
        f"Manufacturer: {part.manufacturer or 'N/A'}\n\n"
        f"Classify this part.  Valid part_kind values: {kinds_str}.\n"
        "Return JSON with these fields:\n"
        "  part_kind   (one of the valid values above, or null if uncertain)\n"
        "  tags        (list of lowercase tag strings)\n"
        "  confidence  (integer 0-100)\n"
    )
    return [
        {"role": "system", "content": _SYSTEM_INSTRUCTION},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from *text*, stripping any markdown fences."""
    stripped = text.strip()
    # Remove ```json ... ``` or ``` ... ``` fences if present
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    return json.loads(stripped)


# ---------------------------------------------------------------------------
# Main service function
# ---------------------------------------------------------------------------

async def run_enrichment(
    job_type: str,
    entity: "Part | Document",
    provider: "AIProvider",
) -> tuple[dict[str, Any], int | None]:
    """Run the AI call for *job_type* against *entity* using *provider*.

    Returns ``(result_json, confidence)`` where confidence is 0-100 or
    ``None`` if the job type does not produce a confidence score.

    Raises any exception on failure — the caller is responsible for catching
    and storing ``error_message``.
    """
    from makervault.ai.base import ChatMessage, CompletionOptions

    # Build messages
    if job_type == "summarise_document":
        raw_messages = _build_summarise_document_messages(entity)  # type: ignore[arg-type]
    elif job_type == "extract_metadata":
        raw_messages = _build_extract_metadata_messages(entity)  # type: ignore[arg-type]
    elif job_type == "generate_aliases":
        raw_messages = _build_generate_aliases_messages(entity)  # type: ignore[arg-type]
    elif job_type == "classify_part":
        raw_messages = _build_classify_part_messages(entity)  # type: ignore[arg-type]
    else:
        raise ValueError(f"Unknown job_type: {job_type!r}")

    messages = [ChatMessage(role=m["role"], content=m["content"]) for m in raw_messages]
    options = CompletionOptions(temperature=0.2, max_tokens=1024)

    response_text = await provider.complete(messages, options)
    result = _extract_json(response_text)

    confidence: int | None = None
    if isinstance(result.get("confidence"), int):
        confidence = max(0, min(100, result["confidence"]))

    return result, confidence
