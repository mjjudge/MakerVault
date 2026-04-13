# Product Vision

## Problem statement

Makers and electronics hobbyists accumulate large numbers of components, boards, tools, and reference documents over time. Finding a specific part, knowing whether you already own it, recalling where it is physically stored, and locating the relevant datasheet are all friction points that slow down building and tinkering. Existing solutions are either too simple (spreadsheets), too complex (ERP systems), or dependent on online services that may become unavailable.

MakerVault solves this by combining inventory tracking, local document preservation, and AI-assisted reasoning into a single self-hosted system designed for real workshop use.

---

## Target users

- Individual makers, hobbyists, and electronics enthusiasts
- Small workshop owners managing a personal or shared component library
- Anyone who has outgrown a spreadsheet but does not need enterprise ERP complexity

---

## Product principles

1. **Local first.** Data, documents, and models should be operable without internet access where possible.
2. **Precision over guessing.** The system tracks what you actually own, not estimates or predictions.
3. **AI assists; the database decides.** AI is used for enrichment, search, and suggestion — not as the inventory record.
4. **Practical, not theoretical.** Every feature should solve a real workshop problem.
5. **Pluggable, not locked in.** No single AI vendor or hosting provider should be required.
6. **Explainable.** When the system makes a suggestion, it should show which parts and documents it is drawing from.

---

## Key capabilities

- Inventory of parts, boards, tools, consumables, and devices
- Hierarchical physical storage locations (room → container → slot)
- Stock instances with quantities, serial numbers, condition, purchase info, and notes
- Local document preservation: datasheets, manuals, schematics, pinouts, receipts, captured vendor pages
- Project records and BOM-style associations between projects and parts
- AI-assisted search: natural language queries grounded in actual inventory
- AI-assisted enrichment: fill in missing part details from stored documents
- AI-assisted project suggestions: "what could I build with what I have?"
- Pluggable AI providers including hosted (OpenAI, Anthropic, DeepSeek) and self-hosted (Ollama, compatible endpoints)

---

## Why local document preservation matters

Vendor pages disappear. Distributor product listings change. Datasheet PDFs move. If the only record of a part's pinout is a link that goes dead, you lose that reference. MakerVault stores a local copy of any document you attach, so technical reference material remains available regardless of what happens upstream.

---

## Why pluggable AI matters

AI capability changes quickly. Locking the system to a single provider creates fragility, ongoing cost obligations, and privacy risks. By treating the AI provider as a swappable component from day one, the system can work with:

- A paid hosted API (e.g. OpenAI, Anthropic) for convenience
- A self-hosted open model (e.g. via Ollama) for privacy and offline use
- A future provider as the landscape evolves

The user should be able to switch or add providers without rewriting application logic.

---

## v1 vision

A single-user, self-hosted web application where a maker can:

1. Add and browse their inventory of parts and tools
2. Assign each item a precise physical location
3. Attach and view local copies of datasheets and notes
4. Search for parts by name, capability, or description
5. See project records and which parts were used
6. Ask AI questions about their inventory, grounded in real data

v1 does not need to be beautiful or feature-complete. It needs to be correct, reliable, and genuinely useful for the workshop use cases above.
