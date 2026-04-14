# BACKLOG

> **Status:** EPICs 0–12 complete.
> **Principle:** Prefer thin vertical slices, grounded data, and early tests over broad speculative build-out.

---

## Delivery principles

- Build the smallest useful vertical slice first.
- Keep the database as the source of truth.
- Treat AI as a reasoning/enrichment layer, not an authority on owned stock.
- Preserve important documents locally from the beginning.
- Keep Docker as the primary runtime model.
- Add tests as soon as a layer appears; do not leave them until “later”.
- Prefer explicit, reviewable changes over clever abstractions.
- Update docs when behaviour, architecture, or domain understanding changes.

---

## Testing strategy from day one

Testing is a first-class concern in MakerVault.

### Expectations
- Every implementation epic should include test work.
- New domain behaviour should have automated tests before or alongside implementation.
- API endpoints should ship with request/response and validation tests.
- Regressions in search, placement, and document linkage should be covered early.
- AI-facing features should be tested for grounding and orchestration, not model creativity.

### Initial test layers
- **Unit tests** for domain logic, validation, helpers, and service functions
- **Integration tests** for database persistence, migrations, and API/database interaction
- **API tests** for endpoint contracts
- **End-to-end tests** for a small number of critical workflows once the UI exists

### Early priorities
- Part vs StockItem separation
- Location vs Container placement rules
- Document linking rules
- Quantity/unit handling
- Search behaviour
- Migration safety for the initial schema

---

## Current proposed implementation order

1. Repo conventions and backlog
2. Docker runtime scaffold
3. Core schema and migrations
4. Basic API and tests
5. Basic web UI and end-to-end smoke tests
6. Document storage and linking
7. Projects and BOM
8. AI provider abstraction
9. AI-assisted workflows
10. Refinement, imports, scanning, mobile-friendly workflows

---

# EPIC 0 — Working conventions and delivery foundation ✅ COMPLETE

## Goal
Make the repository execution-ready so future work is consistent, reviewable, and testable.

## Scope
- Finalise backlog
- Align docs with current product direction
- Add explicit testing expectations to repo guidance
- Define basic contribution and decision-making conventions
- Ensure terminology is consistent across docs

## Tasks
- Create `BACKLOG.md`
- Update `AGENTS.md` to require tests with behaviour changes
- Add a short testing section to `README.md`
- Review `DATA_MODEL.md` for final conceptual fixes
- Add a “likely uniqueness rules” subsection to the data model
- Add `ProjectDocument` to the conceptual model
- Clarify `ProjectPart.is_owned` as derived/cache or remove it
- Clarify stock placement rules
- Clarify denormalised alias handling

## Acceptance criteria
- Repo has a clear backlog and execution order
- Docs use consistent domain language
- Testing is explicitly expected from the first implementation epic
- No doc implies that implementation already exists

## Tests
- No code tests yet required
- Documentation review checklist completed

---

# EPIC 1 — Docker runtime scaffold ✅ COMPLETE

## Goal
Establish Docker Compose as the primary way to run MakerVault locally and on the Ubuntu host.

## Scope
- Compose-based scaffold only
- No real application logic yet
- Persistent storage paths established early

## Tasks
- Add `infra/docker/docker-compose.yml`
- Add `.env.example`
- Define placeholder services:
  - `api`
  - `web`
  - `worker`
  - `postgres`
  - `nginx`
- Define persistent volumes for:
  - Postgres data
  - MakerVault document storage
- Document startup flow in `README.md`
- Document runtime shape in `ARCHITECTURE.md` and `TECHNICAL_SPEC.md`

## Acceptance criteria
- `docker compose up` works with placeholder services
- Document storage is treated as persistent first-class state
- Runtime architecture is documented clearly
- No local non-Docker workflow is assumed as primary

## Tests
- Add a minimal verification script or documented smoke-check workflow
- Optional: basic container healthcheck placeholders where sensible

---

# EPIC 2 — Backend foundation and test harness ✅ COMPLETE

## Goal
Create the backend project skeleton with testing and migration foundations before business features.

## Completed
- FastAPI application in `apps/api/src/makervault/`
- `pyproject.toml` with runtime and dev dependencies
- Pydantic-settings config pattern (`config.py`)
- Async SQLAlchemy engine and session factory (`database.py`)
- Alembic migration tooling (`alembic.ini`, `migrations/env.py`)
- Health endpoint (`GET /api/health`) with DB connectivity check
- Pytest + pytest-asyncio test harness (15 tests, all passing)
- `Dockerfile` for the api service (multi-stage, non-root)
- Nginx reverse proxy config (`infra/nginx/default.conf`)
- `docker-compose.yml` updated to build api from source

## Scope
- API placeholder app
- database connection foundation
- migration tooling
- test harness
- no rich business logic yet

## Tasks
- Create backend project structure under `apps/api`
- Add dependency management
- Add test framework
- Add migration tooling
- Add database settings/config pattern
- Add test database strategy
- Add CI-ready local test commands, even if CI is not added yet
- Add a basic health endpoint

## Acceptance criteria
- Backend app starts in Docker
- Tests can be run locally in a repeatable way
- Migrations can be created and applied
- Health endpoint responds successfully

## Tests
- Health endpoint test
- Database connectivity integration test
- Config loading test
- Migration smoke test

---

# EPIC 3 — Core domain schema: inventory foundations ✅ COMPLETE

## Goal
Implement the first real domain slice for inventory and placement.

## Completed
- Category ORM model with hierarchical self-reference
- Location ORM model with hierarchical self-reference
- Container ORM model with placement rule (location OR parent container, not both)
- Part ORM model with full field set from DATA_MODEL (enums, JSONB, TSVECTOR, arrays)
- StockItem ORM model with placement rule (location OR container, not both)
- Python-side `@validates` guards for dual/null placement violations
- Cross-database compatible `CASE WHEN` check constraints
- Alembic initial migration (`migrations/versions/0001_initial_schema.py`)
- 17 new model tests (32 total, all passing)

## Scope
Initial schema and persistence for:
- Category
- Part
- StockItem
- Location
- Container

## Tasks
- Create initial migrations
- Implement ORM/domain models
- Add constraints and indexes
- Implement placement rules
- Support nested locations and containers
- Support direct stock placement and container placement
- Add basic seed/dev data helpers if useful

## Acceptance criteria
- Parts can exist independently of stock
- StockItems must resolve to a physical placement
- Locations can be hierarchical
- Containers can be nested
- A Part can have multiple StockItems in different places
- Schema reflects the conceptual model closely enough to proceed

## Tests
- Part creation test
- StockItem creation test
- Validation test for invalid placement
- Nested container placement test
- Location hierarchy test
- Constraint/index smoke tests
- Migration round-trip test

---

# EPIC 4 — Basic API: parts, stock, locations, containers ✅ COMPLETE

## Goal
Expose the inventory foundation through a practical REST API.

## Completed
- Pydantic schemas for all 5 resources (Category, Location, Container, Part, StockItem)
- CRUD endpoints (create, read, update, delete, list) for all resources
- Filtering by category, status, part_kind, location, container, part_id
- Pagination (skip/limit) on all list endpoints
- Simple text search over parts (name, code, description, manufacturer, MPN)
- Placement-aware stock retrieval
- Input validation (placement rules, enum values, required fields)
- Part code uniqueness enforced at API level (409 Conflict)
- 31 new API endpoint tests (63 total, all passing)
- OpenAPI docs available at `/api/docs`

## Scope
CRUD and list/search APIs for:
- parts
- stock items
- locations
- containers
- categories

## Tasks
- Define REST routes
- Implement create/read/update/list endpoints
- Add validation schemas
- Add basic filtering
- Add pagination
- Add simple text search over parts
- Add placement-aware stock retrieval

## Acceptance criteria
- A user can create and query Parts
- A user can create StockItems and place them physically
- A user can browse location/container hierarchy
- API validation errors are clear and consistent
- OpenAPI/docs are available if supported by the framework

## Tests
- Endpoint tests for create/read/update/list
- Validation failure tests
- Filtering and pagination tests
- Search tests
- Placement resolution tests
- Database integration tests for core endpoints

---

# EPIC 5 — Basic web UI: search-first inventory workflow ✅ COMPLETE

## Goal
Deliver the first usable interface.

## Completed
- React + Vite + TypeScript SPA scaffolded in `apps/web/`
- `react-router-dom` navigation with 5 routes
- `@tanstack/react-query` for server state management
- `axios` API client with typed interfaces for all 5 resources
- **Home page** — stats (parts/stock/locations count), search-first landing, quick links
- **Parts page** — searchable list view, "+ New Part" modal form
- **Part detail page** — edit-in-place form, delete, stock items table
- **Stock page** — table view of all stock items
- **Locations page** — locations + containers list, create modals
- CSS design system (nav, cards, tables, badges, modals, forms)
- `Dockerfile` for web service (multi-stage: Node build → Nginx runtime)
- Vite dev proxy: `/api` → `http://api:8000`
- `docker-compose.yml` updated: web now builds from `apps/web/Dockerfile`
- 10 component/unit tests (73 total across Python + JS, all passing)
- TypeScript build passes cleanly
- Implement basic navigation
- Implement part list/detail views
- Implement stock placement views
- Implement location/container browsing
- Keep UI fast, plain, and practical

## Acceptance criteria
- A user can search for a part by name or tag
- A user can see where matching stock is stored
- A user can browse from location to nested container to stock
- A user can create and edit basic records through the UI

## Tests
- Component/unit tests for core views
- API mocking tests where appropriate
- End-to-end smoke tests for:
  - create part
  - create stock item
  - assign placement
  - search and find location

---

# EPIC 6 — Documents and local knowledge capture ✅ COMPLETE

## Goal
Make MakerVault a durable technical knowledge store, not just an item register.

## Scope
- Document entity
- local file storage
- document upload
- document linking
- extracted text placeholder pipeline
- project document support

## Tasks
- Implement `Document`
- Implement `PartDocument`
- Implement `StockItemDocument`
- Implement `ProjectDocument`
- Add upload/storage flow
- Store checksums and metadata
- Add extracted text field handling
- Add basic document list/view UI
- Link documents to parts, stock items, and projects

## Acceptance criteria
- A document can be uploaded and stored locally
- A document can be linked to a Part
- A document can be linked to a StockItem
- A document can be linked to a Project
- Document metadata is queryable
- Local document persistence is stable across restarts

## Tests
- Upload/storage integration test
- Checksum test
- Document-linking tests
- File metadata persistence test
- API tests for upload and association
- UI smoke test for attaching and viewing a document

---

# EPIC 7 — Projects and BOM foundations ✅ COMPLETE

## Goal
Model planned and completed builds, and connect them to inventory.

## Scope
- Project
- ProjectPart
- basic BOM availability logic
- usage-ready structure

## Tasks
- Implement project schema and endpoints
- Implement BOM entry schema and endpoints
- Add availability calculation from stock
- Mark `is_owned` as derived/cache if retained
- Add project detail UI
- Add linked parts view
- Add missing-vs-owned BOM summary

## Acceptance criteria
- A project can be created
- Parts can be added to a BOM
- The system can report whether required parts appear to be in stock
- Projects can link to supporting documents
- A user can inspect a project and see candidate owned parts

## Tests
- Project CRUD tests
- BOM entry tests
- Availability calculation tests
- Document linkage tests for projects
- End-to-end test for creating a project and adding parts

---

# EPIC 8 — Search refinement and inventory usability ✅ COMPLETE

## Goal
Make the system genuinely efficient for real workshop use.

## Completed
- `PartAlias` ORM model with normalised alias storage and cascade FK to `parts`
- Alembic migration `0004_part_aliases`
- Part alias router (`GET/POST /parts/{id}/aliases`, `DELETE /parts/{id}/aliases/{alias_id}`)
- Denormalised `Part.aliases` array kept in sync after every alias mutation
- Search (`?q=`) now includes alias matching (via PartAlias subquery — cross-database compatible)
- Tag-based array filter (`?tags[]=`) on `/parts` (PostgreSQL-only)
- `StockItemResponse` enriched with `location_name` and `container_name` (resolved from DB)
- Frontend: alias management section on Part detail page (add/remove aliases inline)
- Frontend: Tags displayed on Part detail page
- Frontend: Stock page shows part names (linked) and resolved placement paths
- Frontend: Part detail stock table shows placement names instead of raw UUIDs
- 19 new backend tests; all 123 tests passing
- 10 frontend tests passing

## Goal
Make the system genuinely efficient for real workshop use.

## Scope
- improved search
- alias support
- capability-aware filtering
- better placement navigation
- quantity/unit edge cases

## Tasks
- Implement `PartAlias`
- Add denormalised alias search support
- Improve full-text and fuzzy search
- Add capability-aware filtering groundwork
- Improve display of resolved placement paths
- Handle countable vs measured stock more cleanly

## Acceptance criteria
- A user can find parts via common names and alternate names
- Search results are useful with partial/fuzzy terms
- Placement paths are displayed clearly
- Basic capability filtering is feasible from stored data

## Tests
- Alias search tests
- Fuzzy/full-text search tests
- Placement path rendering tests
- Quantity/unit logic tests
- Regression tests for search ranking assumptions where practical

---

# EPIC 9 — AI provider abstraction ✅ COMPLETE

## Goal
Introduce AI in a provider-agnostic way without hard-coding one model vendor.

## Completed
- `AIProviderConfig` ORM model — stores provider config in the database; API keys are **never** persisted (stored as env var names only)
- `AIProvider` abstract base class with `complete`, `embed`, and `health_check` interfaces
- `OpenAIProvider` adapter — covers `openai` and `openai_compatible` provider types
- `OllamaProvider` adapter — covers self-hosted Ollama instances
- Provider service (`build_provider`, `get_active_provider`, `get_provider_by_id`) for config loading and adapter selection
- Alembic migration `0005_ai_provider_configs.py`
- `httpx` added as a runtime dependency for HTTP calls to AI endpoints
- REST API: `GET/POST/PATCH/DELETE /api/ai/providers` + `POST /api/ai/providers/{id}/health`
- AI Settings page (`/ai`) in the web UI — list, add, edit, delete, enable/disable, set default, live health-check
- "AI" nav link added to the global navigation bar
- 30 new tests in `test_epic9.py` (153 total, all passing)

## Scope
- provider config
- provider interface/contracts
- grounded orchestration layer
- one hosted provider adapter
- one local/OpenAI-compatible adapter

## Tasks
- ✅ Implement `AIProviderConfig`
- ✅ Define internal interfaces for:
  - chat/reasoning
  - document summarisation
  - metadata extraction
  - project suggestion
  - embeddings later if needed
- ✅ Implement provider selection/config loading
- ✅ Add one hosted adapter (OpenAI / OpenAI-compatible)
- ✅ Add one local adapter (Ollama)
- ✅ Ensure secrets remain outside the database

## Acceptance criteria
- ✅ AI providers can be configured without changing business logic
- ✅ The app can select an enabled provider for a task
- ✅ Grounded context can be passed into AI workflows
- ✅ The abstraction does not assume one permanent provider

## Tests
- ✅ Provider config tests
- ✅ Adapter contract tests
- ✅ Mocked orchestration tests
- ✅ Failure/fallback tests
- ✅ Tests confirming no secrets are persisted in DB records

---

# EPIC 10 — AI enrichment and document understanding ✅ COMPLETE

## Goal
Use AI to enrich stored records and preserved technical documents.

## Scope
- enrichment jobs
- document summarisation
- metadata extraction
- alias generation
- capability extraction

## Tasks
- [x] Implement `EnrichmentJob` ORM model (`enrichment_jobs` table)
- [x] Alembic migration `0006_enrichment_jobs.py`
- [x] Pydantic schemas: `EnrichmentJobCreate`, `EnrichmentJobResponse`, `EnrichmentJobListResponse`
- [x] Enrichment service (`enrichment_service.py`) — four job types with prompt construction, JSON parsing, and markdown-fence stripping
- [x] Router `enrichment.py` — create/run, list (filtered), get, apply, dismiss, delete
- [x] Entity provenance: `provider_id` and `provider_name` stored per job
- [x] Apply workflow: aliases → `PartAlias` rows + denormalised sync; classify_part → `part.part_kind` + tags; summarise_document → `document.summary`; extract_metadata → document fields
- [x] Dismiss workflow: marks job as `dismissed`, validates only `done` jobs can be dismissed
- [x] Frontend: `EnrichmentJob` TypeScript type and `enrichmentApi` added to `client.ts`
- [x] Frontend: `EnrichmentPanel` component — job list, trigger, apply, dismiss, delete, result preview
- [x] Frontend: `EnrichmentPanel` integrated into `PartDetailPage`
- [x] Tests: `test_epic10.py` — 27 tests covering job lifecycle, mocked AI calls, apply/dismiss, provenance, error handling, service unit tests

## Acceptance criteria
- [x] Documents can be enriched via on-demand AI jobs
- [x] Results are stored with traceability (provider_id, provider_name, confidence)
- [x] AI-generated outputs are reviewable before being applied
- [x] Extracted capabilities and aliases improve part detail data
- [x] Failed jobs record a human-readable error message

## Tests
- [x] Job lifecycle tests
- [x] Provenance and confidence tests
- [x] Mocked AI result parsing tests (all four job types)
- [x] Failure/retry tests (no provider, AI error, bad JSON)
- [x] Apply/dismiss conflict tests

---

# EPIC 11 — AI-assisted project inspiration and grounded workflows ✅ COMPLETE

## Goal
Deliver the distinctive MakerVault value: “what can I build with what I already own?”

## Scope
- grounded project suggestions
- parts-for-idea matching
- BOM suggestion using available stock
- “where do I find the suggested parts?” flows

## Completed
- [x] `ProjectSuggestion` ORM model (`project_suggestions` table)
- [x] Alembic migration `0007_project_suggestions.py`
- [x] Pydantic schemas: `ProjectSuggestionCreate`, `ProjectSuggestionResponse`, `ProjectSuggestionListResponse`
- [x] Suggestion service (`suggestion_service.py`) — inventory context builder, AI prompt construction, JSON parsing, normalisation
- [x] Router `suggestions.py` — create/run, list, get, delete
- [x] Entity provenance: `provider_id` and `provider_name` stored per suggestion
- [x] Inventory grounding: parts with available stock are fetched and included in AI prompt context
- [x] Missing parts identification: AI output distinguishes owned vs needed components
- [x] Frontend: `ProjectSuggestion` TypeScript type and `suggestionApi` added to `client.ts`
- [x] Frontend: `SuggestionsPage` component — prompt form, result cards with owned/missing parts breakdown
- [x] Frontend: `/suggestions` route registered in `App.tsx`
- [x] Frontend: “Inspire” nav link added to `Nav.tsx`
- [x] Tests: `test_epic11.py` — 19 tests covering job lifecycle, mocked AI calls, inventory grounding, empty inventory, malformed responses, list/get/delete, service unit tests

## Acceptance criteria
- [x] A user can ask for a project idea using owned parts
- [x] Suggestions cite relevant parts/documents/projects
- [x] The system can distinguish owned vs missing components
- [x] Suggestions are traceable back to grounded records

## Tests
- [x] Orchestration tests with mocked AI providers
- [x] Grounding tests ensuring inventory context is included
- [x] Output parsing/validation tests
- [x] End-to-end test for a basic suggestion flow with fake provider output

---

# EPIC 12 — Usage history and stock lifecycle ✅ COMPLETE

## Goal
Track what was used, consumed, returned, tested, or damaged over time.

## Scope
- UsageHistory
- stock lifecycle events
- quantity changes
- project-linked usage

## Tasks
- Implement `UsageHistory`
- Add allocation/consumption flows
- Add manual movement and status changes
- Add project-linked usage recording
- Add audit-style views for item history

## Acceptance criteria
- Stock changes can be recorded with context
- Usage can be linked to a project
- Consumables can decrement meaningfully
- A user can inspect stock history

## Tests
- Quantity delta tests
- Lifecycle action tests
- Project-linked usage tests
- Audit history retrieval tests

---

# EPIC 13 — Imports, labels, and operational polish

## Goal
Reduce friction for real-world usage and maintenance.

## Scope
- CSV import/export
- label and barcode readiness
- bulk moves
- basic admin utilities
- mobile-friendly improvements

## Tasks
- Add import/export formats
- Add label code support through the UI
- Add bulk relocation workflow
- Add duplicate detection helpers
- Improve small-screen usability
- Add backup/restore guidance for DB + document store

## Acceptance criteria
- A user can import a batch of parts or stock
- A user can export core data
- Containers can be labelled and moved in bulk
- Backup guidance is documented and practical

## Tests
- Import validation tests
- Export format tests
- Bulk move tests
- Mobile UI smoke tests where practical

---

## Not now

Deliberately not in the early roadmap:

- e-commerce ordering flows
- marketplace integrations
- enterprise permissions model
- automated image-based part recognition
- CAD/schematic editing
- manufacturing ERP complexity
- autonomous AI changing inventory without confirmation
- Kubernetes or distributed microservice architecture

---