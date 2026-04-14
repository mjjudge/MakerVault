# Architectural Decisions

This file records architectural decisions using a lightweight ADR (Architecture Decision Record) format.

Each entry has: a title, a status, a context, the decision made, and the consequences.

---

## ADR-001 — Self-hosted first deployment model

**Status:** Accepted

**Context:**
The primary user wants full control over their data, the ability to operate offline, and no dependency on a third-party cloud service for the core system.

**Decision:**
MakerVault is designed to run on a single Ubuntu host using Docker Compose. The system must function fully without internet access except for optional AI provider calls.

**Consequences:**
- Deployment is the user's responsibility
- The system does not need to handle multi-tenant infrastructure
- Backup and maintenance are the user's responsibility
- This simplifies the architecture significantly

---

## ADR-002 — PostgreSQL as primary database

**Status:** Accepted

**Context:**
The system needs structured relational data (parts, stock, locations, projects), text search, and will likely want vector search in the future.

**Decision:**
PostgreSQL 16+ is the primary and only relational database. SQLAlchemy (async) with Alembic for migrations.

**Consequences:**
- Full-text search via PostgreSQL `tsvector` is available from day one
- The pgvector extension can be added later for semantic search without a separate database
- No need to evaluate or maintain multiple database systems

---

## ADR-003 — Local document preservation

**Status:** Accepted

**Context:**
Technical documents (datasheets, manuals, pinouts, vendor pages) go offline regularly. Relying on external URLs for reference material creates long-term data loss risk.

**Decision:**
When a document is attached to a part or project, a local copy is stored on disk in the Docker volume. The original URL is recorded for reference but is not required. The local copy is the authoritative version.

**Consequences:**
- Document storage consumes disk space on the host
- Files are not backed up automatically; the user is responsible for backing up the volume
- The system must manage file storage, MIME types, and access control for stored files

---

## ADR-004 — Pluggable AI provider architecture

**Status:** Accepted

**Context:**
The AI landscape changes rapidly. Locking the system to a single provider (e.g. OpenAI) creates vendor dependency, ongoing cost, and privacy risk. Some users will want fully self-hosted AI.

**Decision:**
The AI layer is designed as a provider abstraction from day one. A common interface (`complete`, `embed`, `health_check`) is implemented for each provider. Provider configuration is stored in the database; secrets come from environment variables. The active provider can be switched at runtime.

**Consequences:**
- More upfront design work in the AI layer
- New providers can be added by implementing the interface without changing application logic
- The system can work with Ollama locally (no internet required) or any OpenAI-compatible endpoint

---

## ADR-005 — Database as source of truth; AI as reasoning layer

**Status:** Accepted

**Context:**
AI language models hallucinate. Using AI output as the inventory record would corrupt the data and erode user trust.

**Decision:**
The database is the sole source of truth for what the user owns, where it is, and what condition it is in. AI is used only for reasoning, enrichment, summarisation, and suggestion. AI outputs that affect the database (e.g. enrichment results) are always shown to the user for confirmation before being saved.

**Consequences:**
- AI features are additive, not authoritative
- Users can trust that what they see in the inventory is what they entered
- Enrichment workflows require a review step

---

---

## ADR-006 — Separate Part from StockItem

**Status:** Accepted

**Context:**
A common shortcut is to store "what a thing is" and "what you own" in a single table (e.g. `item` with `quantity` and `location`). This collapses the abstract definition of a component with the physical inventory record.

**Decision:**
Part and StockItem are modelled as separate entities. Part describes the abstract type ("ESP32 DevKit V1"). StockItem records a physical owned instance or batch ("3 units, Box B, Garage"). A Part may have many StockItems. See `DATA_MODEL.md` for detail.

**Consequences:**
- Parts can be referenced in BOMs without owning any physical stock
- Multiple physical batches of the same part (different locations, conditions, purchase dates) are naturally supported
- Search, duplicate detection, and AI grounding are cleaner
- Slightly more complex data entry, but this is mitigated by UI design

---

## ADR-007 — Separate Location from Container

**Status:** Accepted

**Context:**
A simple approach is to store location as a single text field (e.g. "Garage / Case F / Tray 2"). This loses structure and makes hierarchy, label printing, and bulk moves impossible.

**Decision:**
Location and Container are separate entities. A Location is a physical place (room, building, site). A Container is a storage object within a location (box, tray, drawer). Containers belong to a Location or to another Container, enabling full hierarchy: `Garage → Case F → Tray 2`. See `DATA_MODEL.md` for detail.

**Consequences:**
- Moving an entire case updates only the case's `location_id`; all nested containers and their stock items follow
- "Where is this part?" queries traverse the container/location hierarchy
- Label codes and QR codes can be attached to containers and resolved back to a location path
- Slightly more joins in queries, but the structure pays off in every location-related workflow

---

## ADR-008 — Documents as first-class entities linked via join tables

**Status:** Accepted

**Context:**
The original design gave Document a single nullable `part_id` and `project_id` column. This prevents a document from being linked to multiple entities and creates NULL-heavy foreign keys.

**Decision:**
Documents do not carry hard foreign keys to Part or Project. Instead, `PartDocument` and `StockItemDocument` join tables link documents to their associated entities. This allows one document (e.g. a generic datasheet) to be linked to multiple parts, and allows receipts or photos to be linked to specific stock items rather than part definitions.

**Consequences:**
- A document can be reused across multiple parts without duplication
- Receipts, condition photos, and serial snapshots attach to StockItems rather than Part definitions
- Queries to find all documents for a part require a join, but this is straightforward
- Future: additional join tables can link documents to projects, suppliers, or topics without schema changes to the Document table

---

## Candidate decisions (not yet resolved)

The following decisions have not been finalised. They should be resolved before the relevant phase of implementation begins.

| Topic | Options | Notes |
|---|---|---|
| Worker task queue | Celery + Redis vs. simple DB-backed queue | Redis adds a dependency; DB queue is simpler for a single-user system |
| Authentication | Bearer token (static) vs. session cookie vs. OAuth | Single-user system; simplicity preferred over full OAuth |
| Semantic search | pgvector vs. Qdrant or Chroma | pgvector preferred to avoid a separate service; defer to Phase 5 |
| Frontend routing | React Router vs. TanStack Router | Resolved: React Router in use since Epic 2 |
| File serving | Serve via API (with auth check) vs. Nginx direct with token | API serving is safer; performance may be a consideration for large files |

---

## ADR-009 — CSV as the primary import/export format

**Status:** Accepted

**Context:**
Users need a practical way to bulk-load an existing parts inventory and to take
offline backups of catalogue and stock data without relying on database dumps.
Multiple format options were considered: JSON, CSV, and spreadsheet formats
(XLSX).

**Decision:**
CSV (UTF-8) is the supported import/export format for parts and stock items.
JSON export is deferred.  XLSX is not supported directly; users are expected to
export from Excel/Sheets as "CSV UTF-8" before uploading.

**Consequences:**
- CSV is universally supported by spreadsheet tools and is easy to inspect and
  edit in a text editor
- A blank template CSV is provided for each import type so users do not need to
  know the column layout in advance
- Import is non-destructive: rows with an existing `part_code` are skipped rather
  than overwritten; this prevents accidental data loss during re-imports
- JSON export is straightforward to add in a future epic if needed

---

## ADR-010 — Bulk relocation via a dedicated endpoint

**Status:** Accepted

**Context:**
Moving stock between locations is a frequent real-world operation (e.g. when
reorganising the workshop). Doing this one item at a time via PATCH is tedious.
Options considered: a bulk PATCH on stock items, a separate endpoint, or a
dedicated "move" event stored in UsageHistory.

**Decision:**
A dedicated `POST /api/stock/bulk-move` endpoint accepts a list of stock item
IDs and a single destination (either a location or a container, not both). The
move is committed atomically. IDs that cannot be found are reported rather than
causing the whole operation to fail. The move is not recorded in UsageHistory —
relocation is a physical placement change, not a consumption or lifecycle event.

**Consequences:**
- Simple, predictable API surface
- Partial failure is handled gracefully: the caller receives a `not_found` list
- Not recording moves in UsageHistory keeps history focused on quantity and
  lifecycle events; if relocation history is needed it can be added as an
  optional UsageHistory action type in a future epic

---

## ADR-011 — Duplicate detection via name and MPN equality

**Status:** Accepted

**Context:**
Users may accidentally create duplicate parts (same component, different
`part_code`). Detecting these early avoids inflated catalogues and inventory
queries. Options: fuzzy string matching, tsvector similarity, exact name/MPN
equality.

**Decision:**
Duplicate detection compares normalised (lowercase, trimmed) part names and
manufacturer part numbers. Two parts are flagged as potential duplicates if
they share either attribute. Fuzzy matching (e.g. Levenshtein distance) is
deferred — it requires an extension or additional library and produces more
false positives.

**Consequences:**
- Zero new dependencies
- Catches the most common duplication pattern (copy-paste of the same part name)
- Does not catch typos or near-matches; a fuzzy or vector-based approach can be
  layered on later (see Phase 5 semantic search)
- Results are advisory only — no automatic merging is performed


---

## ADR-012 — Assisted intake as a suggestion layer, not an automatic creator

**Status:** Accepted

**Context:**
Epic 14 introduces a free-text intake path where users describe a part in plain
English and the system suggests matches or generates a new part code. Two models
were considered: (a) automatically create the part record from the description,
or (b) surface suggestions and require the user to confirm before any record is
created.

**Decision:**
Intake is a suggestion layer only. The user's description triggers a candidate
search and code generation, but no Part or StockItem record is created until the
user explicitly chooses an action ("reuse this part" or "create new"). The
`IntakeSuggestion` record is stored for audit purposes but is not authoritative.

**Consequences:**
- Consistent with ADR-005 (database as source of truth; AI does not act without
  confirmation)
- Intake results are reviewable and dismissible
- The suggestion can be revisited if the user does not immediately decide
- Prevents ghost records from speculative intake attempts

---

## ADR-013 — Inventory hygiene surfaced as advisory, not automatic remediation

**Status:** Accepted

**Context:**
Epic 15 introduces hygiene checks — duplicate detection, split-stock visibility,
weak-metadata flags, and a part merge workflow. The question is whether hygiene
issues should trigger automatic fixes (e.g. auto-merge high-confidence
duplicates) or only surface them for human review.

**Decision:**
All hygiene insights are advisory. The system surfaces issues but never
automatically merges, deletes, or modifies records. The part merge endpoint
requires an explicit request with a confirmed source part ID. The `needs_review`
flag is set by automated processes but cleared only by a user action.

**Consequences:**
- Users retain full control over their inventory data
- No risk of silent data loss from an over-confident merge
- Merge operations are auditable (the absorbing part records the event)
- The hygiene dashboard may show stale counts until the user acts; this is
  acceptable for a single-operator system

---

## ADR-014 — Backup records stored in the primary database

**Status:** Accepted

**Context:**
Epic 16 introduces `BackupRecord` to give users visibility over backup history.
Two approaches were considered: (a) store backup metadata in the primary
PostgreSQL database, or (b) write it to a separate sidecar file on the host.

**Decision:**
Backup records are stored in the PostgreSQL `backup_records` table. Backup
scripts (manual or scheduled) call `POST /api/backups` to register a completed
run. The API and UI surface the most recent records without any external tooling.

**Consequences:**
- Backup status is visible in the same UI as the rest of the system
- A backup script can fail to register (e.g. if the DB is unavailable); this
  is an acceptable edge case — a failed backup should be visible as missing
  rather than silently omitted
- The backup records themselves are included in the next database backup, so
  history accumulates correctly over time
- If the database itself is unrecoverable, backup history is also lost; this is
  acceptable because the restore instructions and volume snapshots are the
  authoritative recovery mechanism, not the records table
