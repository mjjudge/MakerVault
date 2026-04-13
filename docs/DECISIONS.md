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

## Candidate decisions (not yet resolved)

The following decisions have not been finalised. They should be resolved before the relevant phase of implementation begins.

| Topic | Options | Notes |
|---|---|---|
| Worker task queue | Celery + Redis vs. simple DB-backed queue | Redis adds a dependency; DB queue is simpler for a single-user system |
| Authentication | Bearer token (static) vs. session cookie vs. OAuth | Single-user system; simplicity preferred over full OAuth |
| Semantic search | pgvector vs. Qdrant or Chroma | pgvector preferred to avoid a separate service; defer to Phase 5 |
| Frontend routing | React Router vs. TanStack Router | No strong preference; decide when web app is scaffolded |
| File serving | Serve via API (with auth check) vs. Nginx direct with token | API serving is safer; performance may be a consideration for large files |
