# Roadmap

This roadmap is broken into phases. Each phase should be functional and stable before the next begins. Phases are not time-boxed here; they are sequence-boxed.

---

## Phase 0 — Scaffold, docs, and bootstrap

> **Status: In progress**

- [x] Repository scaffold with folder structure
- [x] Core documentation: README, AGENTS, PRODUCT_VISION, TECHNICAL_SPEC, DATA_MODEL, ARCHITECTURE, API_SPEC, UX_NOTES, DECISIONS, ROADMAP
- [ ] Docker Compose skeleton (db, api, web, worker placeholders)
- [ ] FastAPI project skeleton in `apps/api` (no routes yet)
- [ ] React + Vite project skeleton in `apps/web` (no pages yet)
- [ ] Alembic migration scaffolding set up
- [ ] `scripts/bootstrap.sh` ready to set up a local development environment

---

## Phase 1 — Core inventory and locations

- [ ] Database schema: Category, Part, StockItem, Location, Container
- [ ] Alembic migrations for Phase 1 entities
- [ ] API endpoints: CRUD for Parts, StockItems, Locations, Containers, Categories
- [ ] Frontend: list and detail views for Parts and StockItems
- [ ] Frontend: location and container hierarchy view
- [ ] Frontend: form to add/edit a Part and its StockItems
- [ ] Basic full-text search over part names, descriptions, and tags (using `search_text` tsvector column)
- [ ] Manual API testing via OpenAPI docs at `/docs`

---

## Phase 2 — Documents and local capture

- [x] Database schema: Document, PartDocument, StockItemDocument, ProjectDocument, Project (stub)
- [x] API: document upload endpoint (PDF, image, and any file type)
- [x] Document storage on local volume with UUID-based paths and SHA-256 checksum
- [x] API: document retrieval and metadata endpoints
- [x] API: link/unlink documents to parts, stock items, and projects via join tables
- [x] Frontend: attach documents to parts (upload + link from Part Detail page)
- [x] Frontend: Documents page — list, search, filter, delete
- [x] Frontend: Documents nav link
- [ ] Frontend: inline PDF and image viewer
- [ ] Frontend: note/text document creation
- [ ] Optional: capture a vendor web page as a locally preserved HTML snapshot

---

## Phase 3 — AI provider abstraction

- [ ] Define AIProvider interface in `apps/api`
- [ ] Implement OpenAI provider adapter
- [ ] Implement Ollama provider adapter
- [ ] Database schema: AIProviderConfig
- [ ] API: endpoints to configure and switch AI providers
- [ ] Frontend: AI provider settings page
- [ ] Health check and connection test per provider
- [ ] At least one additional provider adapter (Anthropic or DeepSeek)

---

## Phase 4 — AI-assisted workflows

- [ ] Database schema: EnrichmentJob, PartAlias, Capability
- [ ] Worker: background enrichment job runner
- [ ] AI-assisted part enrichment: fill missing fields from stored documents
- [ ] AI-generated aliases stored in PartAlias; normalised capabilities stored in Capability
- [ ] AI-assisted search: natural language query over inventory with database grounding
- [ ] AI project suggestion: "what could I build with what I own?"
- [ ] AI capability query: "what parts do I have that can do X?" (grounded in Capability table)
- [ ] Frontend: AI query panel with grounded results (show which parts/documents were used)
- [ ] Frontend: enrichment job status and review

---

## Phase 5 — Polish, imports, mobile workflows, and scanning

- [x] Import from CSV or spreadsheet (basic mapping)
- [ ] QR code or barcode label generation for containers and parts
- [x] Responsive design review and mobile usability improvements
- [ ] Semantic / vector search (pgvector or similar)
- [x] Bulk operations (move stock, update quantities)
- [x] Project status tracking and BOM completion view (using ProjectPart `is_owned`)
- [x] Usage history view per part or project (UsageHistory)
- [x] Data export (JSON, CSV)
- [ ] Performance and reliability hardening
- [x] Documentation review and user-facing help content

---

---

## Phase 6 — Smart intake, hygiene, and operational resilience

- [x] Assisted part intake: free-text description → candidate match list + suggested part code (Epic 14)
- [x] Part code generation service with uniqueness guarantee (Epic 14)
- [x] Duplicate/similarity detection at intake time with confidence scoring (Epic 14)
- [x] "Add stock to existing part" shortcut from the intake workflow (Epic 14)
- [x] Storage suggestion based on historical placement patterns (Epic 14)
- [ ] Inventory hygiene dashboard: missing documents, aliases, capabilities (Epic 15)
- [ ] "Parts stored in multiple locations" split-stock insight (Epic 15)
- [ ] "Possible duplicates" review queue in the UI (Epic 15)
- [ ] Part merge workflow: safely consolidate duplicate Part records (Epic 15)
- [ ] `BackupRecord` model and API endpoints (Epic 16)
- [ ] Backup status widget showing last successful DB and document backup (Epic 16)
- [ ] Scheduled backup job in the worker with failure recording (Epic 16)
- [ ] Restore instructions page/export (Epic 16)

---

## Future / deferred ideas

These are not planned for early phases but are worth noting:

- Integration with supplier APIs for pricing and availability lookup
- Computer vision for part identification from photos
- Advanced permissions model for shared workshop use
- Native mobile app
- Automated stock reorder suggestions
