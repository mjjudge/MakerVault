# Architecture

> **Status:** Docker Compose scaffold is in place. Application services (`api`, `web`, `worker`) are containerised placeholders pending implementation.

---

## System overview

MakerVault is composed of three application processes, a database, a document store, and an AI provider layer. All components are deployed via Docker Compose on a single Ubuntu host.

```
                        ┌─────────────────────────────────────────┐
                        │              Docker host (Ubuntu)        │
                        │                                          │
   Browser ─────────────►  apps/web  (React + Vite, served by     │
                        │            Nginx or Vite dev server)     │
                        │              │                           │
                        │              ▼                           │
                        │  apps/api  (FastAPI / Python)            │
                        │     │          │          │              │
                        │     ▼          ▼          ▼              │
                        │  PostgreSQL  Local     AI Provider       │
                        │  (primary    document   abstraction      │
                        │   database)  store      layer            │
                        │     │       (volume)     │               │
                        │     │                    ▼               │
                        │  apps/worker             External or     │
                        │  (background jobs)       self-hosted     │
                        │                          AI endpoint     │
                        └─────────────────────────────────────────┘
```

---

## Components

### `apps/web` — Frontend

- React + Vite + TypeScript
- Single-page application served via Nginx in production
- Communicates with the API over HTTP (REST)
- Responsible for all user-facing views: inventory browsing, search, document viewer, project management, AI interaction panel

### `apps/api` — Backend API

- FastAPI (Python 3.12+)
- Async SQLAlchemy with Alembic for database migrations
- Exposes a REST API consumed by the frontend and potentially by scripts
- Handles document uploads, stores files to the local document volume, and records metadata in the database
- Dispatches AI queries through the provider abstraction layer
- Enqueues background tasks for the worker

### `apps/worker` — Background Worker

- Python process consuming a task queue
- Handles: document ingestion, AI enrichment jobs, background indexing
- Shares access to the database and document volume with the API
- Task queue mechanism: TBD (Celery + Redis or DB-backed simple queue; see `DECISIONS.md`)

### PostgreSQL

- Primary relational database
- Stores all structured data: inventory, locations, containers, projects, documents metadata, AI provider config, enrichment jobs
- Schema managed via Alembic migrations in `apps/api`

### Local document store

- A Docker volume mounted into both `apps/api` and `apps/worker`
- Stores actual document files (PDFs, images, HTML snapshots) by UUID
- Database holds the file path and metadata; files are never served directly from the filesystem without an API access check

### AI provider layer

- A provider abstraction defined in `apps/api/src/makervault/ai/`
- Each provider implements a consistent interface: `complete(messages)`, `embed(text)` (optional), `health_check()`
- Provider configuration is stored in the `ai_provider_configs` table; secrets (API keys) come from environment variables — **never stored in the database**
- The `api_key_env_var` field records the *name* of the environment variable the adapter reads at runtime
- Supported provider types: `openai`, `openai_compatible`, `ollama`, `anthropic`
- Only one provider needs to be active at a time; multiple can be configured and switched via the AI Settings page (`/ai`)
- Provider management API: `GET/POST/PATCH/DELETE /api/ai/providers` + `POST /api/ai/providers/{id}/health`

### Nginx (reverse proxy)

- In production, Nginx sits in front of both the frontend and the API
- Handles HTTPS termination, static file serving for the frontend, and proxying API requests
- Config lives in `infra/nginx/`

---

## Data flow examples

### Adding a part with a datasheet

1. User submits a new part form in the frontend
2. Frontend POSTs to `POST /api/parts` and `POST /api/documents` (with file upload)
3. API saves part record to PostgreSQL and file to the document volume
4. Worker optionally picks up an enrichment job to extract metadata from the PDF

### Searching inventory

1. User types a natural-language query
2. Frontend sends request to `GET /api/search?q=...` or `POST /api/ai/query`
3. API queries PostgreSQL (full-text search)
4. If AI search is requested, the API calls the active AI provider with inventory context
5. Results are returned to the frontend, clearly indicating which are database results and which are AI-augmented

### AI project suggestion

1. User requests "suggest projects based on my inventory"
2. API queries the database for all owned parts and their capabilities
3. API calls the active AI provider with an inventory summary prompt
4. Response is returned to the frontend with source references (which parts the suggestion is based on)

---

## Deployment topology

```
Host: Ubuntu server (single machine)

infra/docker/docker-compose.yml
├── nginx     (reverse proxy)          port 80 → host
├── web       (React app via Nginx)    internal only
├── api       (FastAPI)                internal only
├── worker    (Python background)      no external port
└── db        (PostgreSQL 16)          internal only

Named volumes:
├── db_data      → /var/lib/postgresql/data   (database, persistent)
└── documents    → /data/makervault/documents (document store, persistent)
```

All services communicate over the private `makervault_net` bridge network. Only `nginx` is exposed to the host. The document volume (`documents`) is mounted into both `api` and `worker` — it must not be deleted.

---

## Future considerations

- **Semantic search:** pgvector extension on PostgreSQL is the preferred path to avoid a separate vector database. Deferred to Phase 5.
- **Mobile:** Responsive web design is the initial approach. A dedicated mobile app is a non-goal for now.
- **Multi-user:** The system is designed for a single operator. Multi-user support is a non-goal for the initial phase but should not be actively designed against.

---

## Phase 6 additions (Epics 14–16)

### Assisted intake service

A new `intake_service` in `apps/api/src/makervault/` will handle free-text part descriptions. It normalises input, searches existing parts for candidates (using full-text and fuzzy matching), generates a unique part code suggestion, and queries historical stock placement patterns to suggest a likely storage location. Results are returned as an `IntakeSuggestion` and require explicit user confirmation before any record is created.

### Inventory hygiene service

A `hygiene_service` will compute and cache inventory health metrics: duplicate candidates, split-stock parts, weak-metadata flags, and the `needs_review` queue. Metrics are surfaced as a summary dashboard and per-category detail pages. Part merge is a dedicated transactional endpoint that moves all linked records (stock, aliases, capabilities, documents) from a source part to a target and deletes the source.

### Backup scheduling and records

The worker will optionally run a scheduled backup job (cron-style, configured via environment variables). Each backup attempt — whether triggered by the scheduler, the API, or a manual script — writes a `BackupRecord` to the database via `POST /api/backups`. The API exposes backup status at `GET /api/backups/latest`. Backup execution uses Docker-native volume snapshots (see backup guidance in `HOWTO.md`).
