# Technical Specification

> **Status:** Planning phase. No implementation has begun. This document describes intended direction, not current state.

---

## Goals

- Provide a self-hosted, Docker-deployable application for inventory and knowledge management
- Support full-text and AI-assisted search over inventory and stored documents
- Preserve technical documents (PDFs, images, HTML snapshots) locally on disk
- Support multiple AI providers through a consistent abstraction layer
- Keep the system simple enough for a single operator to run and maintain

---

## Non-goals (initial phase)

- Multi-tenant or multi-user authentication
- Supplier API integrations or automatic ordering
- Computer vision for part identification
- Full mobile application (responsive web is sufficient initially)
- Vector database or semantic search infrastructure (deferred to a later phase)
- Kubernetes or distributed deployment
- Real-time collaboration

---

## Initial architecture direction

The system is composed of three main application processes:

| Process | Role |
|---|---|
| `apps/api` | FastAPI backend; serves REST API, handles business logic, manages DB access |
| `apps/web` | React + Vite frontend; user interface |
| `apps/worker` | Background worker; handles async tasks such as document ingestion and AI enrichment |

All three are deployed via Docker Compose. PostgreSQL is the primary database. Documents are stored on a local filesystem volume mounted into the API and worker containers.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for a diagram.

---

## Core services

### API (`apps/api`)

- Language: Python 3.12+
- Framework: FastAPI
- ORM: SQLAlchemy (async) with Alembic for migrations
- Authentication: simple token or session auth (single-user initially)
- Responsibilities: CRUD for all entities, document upload/retrieval, AI query dispatch, search

### Frontend (`apps/web`)

- Language: TypeScript
- Framework: React + Vite
- Responsibilities: inventory browsing, search UI, document viewer, project management, AI interaction panel

### Worker (`apps/worker`)

- Language: Python
- Queue: task queue (e.g. Celery with Redis, or a simple DB-backed queue — TBD)
- Responsibilities: document processing, AI enrichment jobs, background indexing

### Database

- PostgreSQL 16+
- Managed via Alembic migrations
- No ORM-level soft-delete magic; explicit fields where needed

### Document store

- Local filesystem directory mounted as a Docker volume
- Files stored by UUID with metadata in the DB
- Subdirectories by entity type for clarity (e.g. `documents/parts/`, `documents/projects/`)

---

## AI integration approach

- A single `AIProvider` abstraction interface is defined in `apps/api`
- Each provider implements: `complete(prompt)`, `embed(text)` (optional), `health_check()`
- Provider configuration (type, endpoint, API key) is stored in the database and/or environment variables
- Multiple providers can be configured; the active provider is selected per request or per task
- Supported provider types (planned): OpenAI, Anthropic, Ollama, DeepSeek, OpenAI-compatible endpoint
- **The database is the source of truth.** AI outputs are used for enrichment and suggestion only; they do not modify the inventory without user confirmation

---

## Storage approach

| Data type | Storage |
|---|---|
| Structured inventory data | PostgreSQL |
| Document files (PDFs, images, HTML) | Local filesystem volume |
| AI provider config | PostgreSQL + environment variables for secrets |
| Enrichment job results | PostgreSQL |
| Semantic vectors (future) | pgvector extension or separate store (deferred) |

---

## Security and privacy considerations

- API should not be exposed to the internet without authentication
- AI API keys are stored as environment variables, not in the database
- Document storage should not be directly served by the API without access control checks
- No telemetry, analytics, or external calls except to explicitly configured AI provider endpoints
- Self-hosted AI (Ollama) should be the default recommendation for privacy-sensitive users

---

## Phased implementation notes

See [`ROADMAP.md`](ROADMAP.md) for the full phased plan. Summary:

- **Phase 0:** Scaffold, docs, Docker skeleton
- **Phase 1:** Core inventory (parts, stock, locations, containers)
- **Phase 2:** Documents and local capture
- **Phase 3:** AI provider abstraction layer
- **Phase 4:** AI-assisted workflows
- **Phase 5:** Polish, imports, mobile workflows

Implementation should not jump ahead. Each phase should be functional and stable before the next begins.

---

## Open questions / decisions needed

See [`DECISIONS.md`](DECISIONS.md) for a record of choices made and options still open.

- Task queue approach for the worker (Celery + Redis vs. DB-backed simple queue)
- Authentication strategy (API key, session, or OAuth for single user)
- Whether to use pgvector for semantic search in Phase 5 or a separate vector store
