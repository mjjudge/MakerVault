"""Part intake service — normalisation, candidate matching, code generation,
and storage suggestion.

All logic is pure-Python with no AI provider dependency so the intake
workflow is available even when no AI provider is configured.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Lookup tables used for normalisation and code-prefix generation
# ---------------------------------------------------------------------------

# Maps description keywords → part-type prefix (for code generation)
_KIND_PREFIXES: list[tuple[set[str], str]] = [
    ({"resistor", "res", "resistance"}, "RES"),
    ({"capacitor", "cap", "capacitance"}, "CAP"),
    ({"inductor", "ind", "inductance", "coil", "choke"}, "IND"),
    ({"diode"}, "DIODE"),
    ({"led", "light emitting"}, "LED"),
    ({"transistor", "bjt", "mosfet", "fet", "jfet"}, "TRANS"),
    ({"microcontroller", "mcu", "microprocessor", "cpu"}, "MCU"),
    ({"esp32", "esp8266", "esp"}, "MCU"),
    ({"arduino"}, "MCU"),
    ({"raspberry"}, "MCU"),
    ({"ic", "integrated circuit", "chip", "opamp", "op-amp", "amplifier", "amp"}, "IC"),
    ({"sensor", "dht", "bme", "bmp", "ds18"}, "SENSOR"),
    ({"relay"}, "RELAY"),
    ({"crystal", "oscillator", "xtal"}, "XTAL"),
    ({"connector", "header", "socket", "plug", "jack"}, "CONN"),
    ({"switch", "button", "pushbutton", "pb"}, "SW"),
    ({"display", "lcd", "oled", "screen", "tft"}, "DISP"),
    ({"motor", "servo", "stepper"}, "MOTOR"),
    ({"module", "board", "dev board", "breakout"}, "MOD"),
    ({"cable", "wire", "ribbon"}, "CABLE"),
    ({"battery", "cell", "lipo", "nimh"}, "BAT"),
    ({"fuse"}, "FUSE"),
    ({"transformer", "xfmr"}, "XFMR"),
    ({"regulator", "ldo", "vreg"}, "REG"),
    ({"power supply", "psu"}, "PSU"),
    ({"pcb", "printed circuit"}, "PCB"),
    ({"tool"}, "TOOL"),
]

# Common stop words to strip from tokens
_STOP_WORDS = frozenset(
    {
        "a", "an", "the", "of", "for", "and", "or", "in", "on", "at", "to",
        "with", "by", "as", "is", "it", "be", "this", "that", "some", "piece",
        "type", "pack", "pcs", "pce", "lot", "set", "each", "unit", "units",
    }
)

# Package designator patterns  (normalise common variants)
_PACKAGE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b0201\b", re.I), "0201"),
    (re.compile(r"\b0402\b", re.I), "0402"),
    (re.compile(r"\b0603\b", re.I), "0603"),
    (re.compile(r"\b0805\b", re.I), "0805"),
    (re.compile(r"\b1206\b", re.I), "1206"),
    (re.compile(r"\b1210\b", re.I), "1210"),
    (re.compile(r"\bsmd\b", re.I), "SMD"),
    (re.compile(r"\bsmt\b", re.I), "SMD"),
    (re.compile(r"\bthrou?gh.?hole\b", re.I), "THT"),
    (re.compile(r"\btht\b", re.I), "THT"),
    (re.compile(r"\bsot.?23\b", re.I), "SOT23"),
    (re.compile(r"\bsot.?223\b", re.I), "SOT223"),
    (re.compile(r"\bto.?92\b", re.I), "TO92"),
    (re.compile(r"\bto.?220\b", re.I), "TO220"),
    (re.compile(r"\bdip\b", re.I), "DIP"),
    (re.compile(r"\bsoic\b", re.I), "SOIC"),
    (re.compile(r"\bqfp\b", re.I), "QFP"),
    (re.compile(r"\bqfn\b", re.I), "QFN"),
    (re.compile(r"\bbga\b", re.I), "BGA"),
]

# Value patterns:  10k, 100nF, 3.3V, 1uH, etc.
# Uses \s? (optional single space) instead of \s* to avoid polynomial ReDoS
# on pathological inputs with many repeated spaces.
_VALUE_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s?(k|M|G|m|u|µ|n|p)?\s?(ohm|ohms|Ω|F|H|V|A|W|hz|Hz)\b"
    r"|\b(\d+(?:\.\d+)?)\s?(k|M|G)?\s?(r|R|ohm|ohms)\b"
    r"|\b(\d+(?:\.\d+)?)\s?(k|K)\b"
    r"|\b(\d+(?:\.\d+)?)\s?(m|u|µ|n|p)(F|H)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


@dataclass
class NormalisedDescription:
    """Result of normalising a free-text part description."""

    raw: str
    tokens: list[str]
    package_hint: str | None = None
    value_hints: list[str] = field(default_factory=list)
    kind_prefix: str | None = None


def normalise_description(description: str) -> NormalisedDescription:
    """Normalise *description* to a structured representation.

    Steps:
    1. Lowercase and strip.
    2. Extract package designators.
    3. Extract value hints (e.g. "10k", "100nF").
    4. Tokenise (split on whitespace and punctuation).
    5. Remove stop words.
    6. Infer a part-type prefix for code generation.
    """
    text = description.strip()

    # --- Package extraction -------------------------------------------------
    package_hint: str | None = None
    for pattern, canonical in _PACKAGE_PATTERNS:
        if pattern.search(text):
            package_hint = canonical
            break

    # --- Value extraction ---------------------------------------------------
    value_hints = [m.group(0) for m in _VALUE_RE.finditer(text)]

    # --- Tokenise -----------------------------------------------------------
    lower = text.lower()
    # Replace punctuation (keep hyphens inside tokens) with spaces
    cleaned = re.sub(r"[^\w\s-]", " ", lower)
    raw_tokens = cleaned.split()
    tokens = [t for t in raw_tokens if t and t not in _STOP_WORDS and len(t) > 1]

    # --- Kind prefix --------------------------------------------------------
    kind_prefix: str | None = None
    for keywords, prefix in _KIND_PREFIXES:
        for kw in keywords:
            if kw in lower:
                kind_prefix = prefix
                break
        if kind_prefix:
            break

    return NormalisedDescription(
        raw=description,
        tokens=tokens,
        package_hint=package_hint,
        value_hints=value_hints,
        kind_prefix=kind_prefix,
    )


# ---------------------------------------------------------------------------
# Candidate scoring helpers
# ---------------------------------------------------------------------------


def _token_set(text: str | None) -> set[str]:
    """Tokenise *text* into a lowercase word set (for overlap scoring)."""
    if not text:
        return set()
    lower = text.lower()
    cleaned = re.sub(r"[^\w\s-]", " ", lower)
    return {t for t in cleaned.split() if t and len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _substring_score(haystack: str | None, needle: str) -> int:
    """Return 30 if *needle* is a substring of *haystack* (case-insensitive)."""
    if not haystack or not needle:
        return 0
    return 30 if needle.lower() in haystack.lower() else 0


def score_candidate(
    part_name: str,
    part_aliases: list[str] | None,
    part_mpn: str | None,
    part_short_desc: str | None,
    normed: NormalisedDescription,
) -> int:
    """Compute a 0–100 confidence score for one candidate part.

    Scoring components (sum, capped at 100):
    - Jaccard overlap between description tokens and part-name tokens: 0–50
    - Exact package match (package_hint in part tokens): +15
    - MPN substring match: +20
    - Alias token overlap bonus: +15
    """
    query_tokens = set(normed.tokens)

    # Name/description overlap
    name_tokens = _token_set(part_name) | _token_set(part_short_desc)
    alias_tokens: set[str] = set()
    for alias in (part_aliases or []):
        alias_tokens |= _token_set(alias)
    all_part_tokens = name_tokens | alias_tokens

    jaccard = _jaccard(query_tokens, all_part_tokens)
    base = int(jaccard * 50)

    # Package hint bonus
    package_bonus = 0
    if normed.package_hint:
        if normed.package_hint.lower() in all_part_tokens:
            package_bonus = 15

    # MPN substring match
    mpn_bonus = 0
    if part_mpn:
        mpn_tokens = _token_set(part_mpn)
        if query_tokens & mpn_tokens:
            mpn_bonus = 20

    # Alias bonus
    alias_bonus = 0
    if alias_tokens:
        alias_jaccard = _jaccard(query_tokens, alias_tokens)
        alias_bonus = int(alias_jaccard * 15)

    return min(100, base + package_bonus + mpn_bonus + alias_bonus)


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

# Separator character for generated codes
_SEP = "-"


def _build_code_prefix(normed: NormalisedDescription) -> str:
    """Build the prefix part of the generated code from the normalised description.

    Examples:
      "10k resistor 0603"  → "RES-10K-0603"
      "ESP32 dev board"    → "MCU-ESP32"
      "DHT22 temp sensor"  → "SENSOR-DHT22"
    """
    parts: list[str] = []

    if normed.kind_prefix:
        parts.append(normed.kind_prefix)

    # Add the most prominent value hint (first one), normalised to uppercase
    if normed.value_hints:
        val = re.sub(r"\s+", "", normed.value_hints[0]).upper()
        parts.append(val)

    # Add package hint
    if normed.package_hint:
        parts.append(normed.package_hint)

    # If we only have a prefix so far (or nothing), try to add the most
    # descriptive non-stop-word token that's not already in the prefix.
    existing_lower = {p.lower() for p in parts}
    for tok in normed.tokens:
        if tok.lower() not in existing_lower and not tok.isdigit() and len(tok) > 2:
            if tok.lower() not in _STOP_WORDS:
                parts.append(tok.upper())
                break

    if not parts:
        # Fallback: take up to 3 tokens from the description
        parts = [t.upper() for t in normed.tokens[:3]]

    return _SEP.join(parts) if parts else "PART"


async def suggest_part_code(description: str, db: AsyncSession) -> str:
    """Generate a unique, human-readable part code from *description*.

    The generated code has the form:  ``PREFIX-NNN``  where PREFIX is derived
    from the description and NNN is a zero-padded sequence number that makes
    the code unique within the current database.

    E.g.  "10k resistor 0603"  →  "RES-10K-0603-001"
    """
    from makervault.models.part import Part

    normed = normalise_description(description)
    prefix = _build_code_prefix(normed)

    # Find all existing codes with this prefix to determine the next sequence
    result = await db.execute(
        select(Part.part_code).where(
            Part.part_code.like(f"{prefix}{_SEP}%")
        )
    )
    existing_codes = {row[0] for row in result.all()}

    # Also check if the prefix itself exists as a code
    check = await db.execute(
        select(Part.part_code).where(Part.part_code == prefix)
    )
    if check.scalar_one_or_none() is not None:
        existing_codes.add(prefix)

    # Find lowest available sequence number
    seq = 1
    while True:
        candidate = f"{prefix}{_SEP}{seq:03d}"
        if candidate not in existing_codes:
            return candidate
        seq += 1


# ---------------------------------------------------------------------------
# Candidate matching
# ---------------------------------------------------------------------------

_MIN_CONFIDENCE = 10  # Candidates below this score are excluded


async def find_candidates(
    description: str,
    db: AsyncSession,
    limit: int = 5,
    category_id: uuid.UUID | None = None,
) -> list[dict]:
    """Load active parts from *db* and return ranked match candidates.

    Each candidate dict has keys: ``part_id``, ``part_code``, ``name``,
    ``short_description``, ``manufacturer``, ``manufacturer_part_number``,
    ``part_kind``, ``confidence``, ``match_reason``.
    """
    from makervault.models.part import Part

    normed = normalise_description(description)

    query = select(Part).where(Part.is_active.is_(True))
    if category_id is not None:
        query = query.where(Part.category_id == category_id)

    result = await db.execute(query.order_by(Part.name))
    parts = result.scalars().all()

    scored: list[tuple[int, dict]] = []
    for p in parts:
        aliases = list(p.aliases) if p.aliases else []
        confidence = score_candidate(
            part_name=p.name,
            part_aliases=aliases,
            part_mpn=p.manufacturer_part_number,
            part_short_desc=p.short_description,
            normed=normed,
        )
        if confidence < _MIN_CONFIDENCE:
            continue

        # Build a human-readable match reason
        reasons: list[str] = []
        name_tokens = _token_set(p.name)
        overlap = set(normed.tokens) & name_tokens
        if overlap:
            reasons.append(f"name matches: {', '.join(sorted(overlap))}")
        if normed.package_hint and normed.package_hint.lower() in _token_set(p.name) | {
            a.lower() for a in aliases
        }:
            reasons.append(f"package match ({normed.package_hint})")
        if p.manufacturer_part_number and any(
            t in p.manufacturer_part_number.lower() for t in normed.tokens
        ):
            reasons.append("MPN match")
        if not reasons:
            reasons.append("partial keyword overlap")

        scored.append(
            (
                confidence,
                {
                    "part_id": p.id,
                    "part_code": p.part_code,
                    "name": p.name,
                    "short_description": p.short_description,
                    "manufacturer": p.manufacturer,
                    "manufacturer_part_number": p.manufacturer_part_number,
                    "part_kind": p.part_kind,
                    "confidence": confidence,
                    "match_reason": "; ".join(reasons),
                },
            )
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


# ---------------------------------------------------------------------------
# Storage suggestion
# ---------------------------------------------------------------------------

# Minimum Jaccard similarity between description tokens and a part's name
# tokens for that part to be considered "similar" when building the storage
# suggestion pool.  0.05 means at least one token in common out of ~20.
_MIN_STORAGE_SIMILARITY = 0.05

# Fixed confidence boost added to frequency-derived storage scores to ensure
# that even a single historical placement produces a non-trivial suggestion
# score (frequency score alone can round to zero for rare placements).
_STORAGE_CONFIDENCE_BOOST = 20


def _storage_score(count: int, total: int) -> int:
    """Compute a 0–100 storage suggestion confidence score.

    Combines a frequency-derived percentage with a fixed base boost, capped
    at 100 so the result is always a valid confidence value.
    """
    return min(100, int(count / total * 100) + _STORAGE_CONFIDENCE_BOOST)


async def suggest_storage(
    description: str,
    db: AsyncSession,
    category_id: uuid.UUID | None = None,
    limit: int = 3,
) -> list[dict]:
    """Suggest storage placements based on historical stock placement patterns.

    Strategy:
    1. Find parts whose names or descriptions are similar to *description*.
    2. Collect the location / container frequencies of their stock items.
    3. Return the most frequent placements as suggestions.

    Returns a list of dicts with keys: ``location_id``, ``container_id``,
    ``name``, ``score``, ``reason``.

    Uses raw SQL for placement lookups so the function works on both SQLite
    (testing) and PostgreSQL (production) without UUID type-binding issues.
    """
    from makervault.models.part import Part

    normed = normalise_description(description)

    # Load active parts using the ORM query (works on both backends)
    query = select(Part).where(Part.is_active.is_(True))
    if category_id is not None:
        query = query.where(Part.category_id == category_id)
    result = await db.execute(query)
    all_parts = result.scalars().all()

    # Identify similar parts by token overlap
    # Store IDs as normalised strings to avoid UUID dialect differences
    similar_id_strs: list[str] = []
    for p in all_parts:
        tok = _token_set(p.name) | _token_set(p.short_description)
        if _jaccard(set(normed.tokens), tok) >= _MIN_STORAGE_SIMILARITY:
            # Convert to string regardless of what the ORM returns (UUID or str)
            similar_id_strs.append(str(p.id))

    if not similar_id_strs:
        return []

    # Fetch stock placement for similar parts using raw SQL to avoid
    # UUID binding differences between PostgreSQL and SQLite.
    if len(similar_id_strs) == 1:
        stock_rows = (
            await db.execute(
                text(
                    "SELECT location_id, container_id FROM stock_items "
                    "WHERE part_id = :pid AND status = 'available'"
                ),
                {"pid": similar_id_strs[0]},
            )
        ).fetchall()
    else:
        placeholders = ", ".join(f":id{i}" for i in range(len(similar_id_strs)))
        params = {f"id{i}": v for i, v in enumerate(similar_id_strs)}
        stock_rows = (
            await db.execute(
                text(
                    f"SELECT location_id, container_id FROM stock_items "
                    f"WHERE part_id IN ({placeholders}) AND status = 'available'"
                ),
                params,
            )
        ).fetchall()

    location_counts: Counter = Counter()
    container_counts: Counter = Counter()
    for row in stock_rows:
        if row.location_id:
            location_counts[str(row.location_id)] += 1
        elif row.container_id:
            container_counts[str(row.container_id)] += 1

    if not location_counts and not container_counts:
        return []

    suggestions: list[dict] = []
    total = sum(location_counts.values()) + sum(container_counts.values()) or 1

    # Top locations — look up by raw SQL to avoid UUID type binding issues
    for loc_id_str, count in location_counts.most_common(limit):
        row = (
            await db.execute(
                text("SELECT name FROM locations WHERE id = :id"),
                {"id": loc_id_str},
            )
        ).fetchone()
        if row is None:
            continue
        suggestions.append(
            {
                "location_id": uuid.UUID(loc_id_str),
                "container_id": None,
                "name": row.name,
                "score": _storage_score(count, total),
                "reason": f"Used by {count} similar part(s)",
            }
        )

    # Top containers (fill remaining slots)
    remaining = limit - len(suggestions)
    for cont_id_str, count in container_counts.most_common(remaining):
        row = (
            await db.execute(
                text("SELECT name FROM containers WHERE id = :id"),
                {"id": cont_id_str},
            )
        ).fetchone()
        if row is None:
            continue
        suggestions.append(
            {
                "location_id": None,
                "container_id": uuid.UUID(cont_id_str),
                "name": row.name,
                "score": _storage_score(count, total),
                "reason": f"Used by {count} similar part(s)",
            }
        )

    suggestions.sort(key=lambda x: x["score"], reverse=True)
    return suggestions[:limit]


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def run_intake_match(
    description: str,
    db: AsyncSession,
    category_id: uuid.UUID | None = None,
) -> dict:
    """Orchestrate: normalise + match + code + storage.

    Returns a dict matching the ``IntakeMatchResponse`` schema.
    """
    normed = normalise_description(description)
    candidates = await find_candidates(description, db, limit=5, category_id=category_id)
    suggested_code = await suggest_part_code(description, db)
    storage = await suggest_storage(description, db, category_id=category_id)

    return {
        "description": description,
        "normalised_tokens": normed.tokens,
        "candidates": candidates,
        "suggested_part_code": suggested_code,
        "storage_suggestions": storage,
    }
