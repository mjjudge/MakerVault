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

- [ ] Database schema: Document, PartDocument, StockItemDocument
- [ ] API: document upload endpoint (PDF, image, HTML)
- [ ] Document storage on local volume with UUID-based paths
- [ ] API: document retrieval with access control check
- [ ] API: link/unlink documents to parts and stock items via join tables
- [ ] Frontend: attach documents to parts or stock items
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

- [ ] Import from CSV or spreadsheet (basic mapping)
- [ ] QR code or barcode label generation for containers and parts
- [ ] Responsive design review and mobile usability improvements
- [ ] Semantic / vector search (pgvector or similar)
- [ ] Bulk operations (move stock, update quantities)
- [ ] Project status tracking and BOM completion view (using ProjectPart `is_owned`)
- [ ] Usage history view per part or project (UsageHistory)
- [ ] Data export (JSON, CSV)
- [ ] Performance and reliability hardening
- [ ] Documentation review and user-facing help content

---

## Future / deferred ideas

These are not planned for early phases but are worth noting:

- Integration with supplier APIs for pricing and availability lookup
- Computer vision for part identification from photos
- Advanced permissions model for shared workshop use
- Native mobile app
- Automated stock reorder suggestions
