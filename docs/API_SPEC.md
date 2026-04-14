# API Specification

## Approach

- REST-first API served by FastAPI
- All endpoints under `/api/v1/` prefix
- JSON request and response bodies
- Standard HTTP status codes
- OpenAPI documentation auto-generated at `/api/docs` (FastAPI default)
- Authentication: TBD — likely bearer token or session cookie for single-user deployment

---

## Resource groups

### Categories

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/categories` | List all categories (tree or flat) |
| POST | `/api/v1/categories` | Create a category |
| GET | `/api/v1/categories/{id}` | Get a category |
| PATCH | `/api/v1/categories/{id}` | Update a category |
| DELETE | `/api/v1/categories/{id}` | Delete a category |
| GET | `/api/v1/categories/{id}/parts` | List parts in a category |

### Parts

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/parts` | List all parts (with pagination and filters) |
| POST | `/api/v1/parts` | Create a new part |
| GET | `/api/v1/parts/{id}` | Get a single part |
| PATCH | `/api/v1/parts/{id}` | Update a part |
| DELETE | `/api/v1/parts/{id}` | Delete a part |
| GET | `/api/v1/parts/{id}/stock` | List all stock items for a part |
| GET | `/api/v1/parts/{id}/documents` | List documents attached to a part (via PartDocument) |
| POST | `/api/v1/parts/{id}/documents` | Attach an existing document to a part |
| DELETE | `/api/v1/parts/{id}/documents/{document_id}` | Detach a document from a part |
| GET | `/api/v1/parts/{id}/projects` | List projects that use this part |
| GET | `/api/v1/parts/{id}/aliases` | List aliases for a part |
| POST | `/api/v1/parts/{id}/aliases` | Add an alias to a part |
| DELETE | `/api/v1/parts/{id}/aliases/{alias_id}` | Remove an alias |
| GET | `/api/v1/parts/{id}/capabilities` | List capabilities for a part |
| POST | `/api/v1/parts/{id}/capabilities` | Add a capability to a part |
| PATCH | `/api/v1/parts/{id}/capabilities/{capability_id}` | Update a capability |
| DELETE | `/api/v1/parts/{id}/capabilities/{capability_id}` | Remove a capability |

### Stock

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/stock` | List all stock items (with filters by part, location, container) |
| POST | `/api/v1/stock` | Create a stock item |
| GET | `/api/v1/stock/{id}` | Get a stock item |
| PATCH | `/api/v1/stock/{id}` | Update a stock item (quantity, condition, location) |
| DELETE | `/api/v1/stock/{id}` | Remove a stock item |
| POST | `/api/v1/stock/{id}/move` | Move a stock item to a different container or location |
| GET | `/api/v1/stock/{id}/history` | Get usage history for a stock item |
| GET | `/api/v1/stock/{id}/documents` | List documents attached to a stock item (via StockItemDocument) |
| POST | `/api/v1/stock/{id}/documents` | Attach an existing document to a stock item |
| DELETE | `/api/v1/stock/{id}/documents/{document_id}` | Detach a document from a stock item |

### Locations

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/locations` | List all locations |
| POST | `/api/v1/locations` | Create a location |
| GET | `/api/v1/locations/{id}` | Get a location |
| PATCH | `/api/v1/locations/{id}` | Update a location |
| DELETE | `/api/v1/locations/{id}` | Delete a location |
| GET | `/api/v1/locations/{id}/containers` | List containers in a location |

### Containers

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/containers` | List all containers |
| POST | `/api/v1/containers` | Create a container |
| GET | `/api/v1/containers/{id}` | Get a container |
| PATCH | `/api/v1/containers/{id}` | Update a container |
| DELETE | `/api/v1/containers/{id}` | Delete a container |
| GET | `/api/v1/containers/{id}/stock` | List stock items in a container |

### Documents

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/documents` | List all documents |
| POST | `/api/v1/documents` | Upload and create a document (multipart form) |
| GET | `/api/v1/documents/{id}` | Get document metadata |
| GET | `/api/v1/documents/{id}/file` | Download or stream the document file |
| PATCH | `/api/v1/documents/{id}` | Update document metadata |
| DELETE | `/api/v1/documents/{id}` | Delete a document and its file |

### Projects

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/projects` | List all projects |
| POST | `/api/v1/projects` | Create a project |
| GET | `/api/v1/projects/{id}` | Get a project |
| PATCH | `/api/v1/projects/{id}` | Update a project |
| DELETE | `/api/v1/projects/{id}` | Delete a project |
| GET | `/api/v1/projects/{id}/parts` | Get the BOM for a project |
| POST | `/api/v1/projects/{id}/parts` | Add a part to a project BOM |
| PATCH | `/api/v1/projects/{id}/parts/{part_id}` | Update a BOM entry |
| DELETE | `/api/v1/projects/{id}/parts/{part_id}` | Remove a part from a BOM |

### AI

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/ai/query` | Natural language query grounded in inventory |
| POST | `/api/v1/ai/suggest-projects` | Request project suggestions based on owned inventory |
| POST | `/api/v1/ai/enrich-part/{id}` | Trigger AI enrichment for a specific part |
| POST | `/api/v1/ai/embed-document/{id}` | Trigger document embedding/indexing job |
| GET | `/api/v1/ai/providers` | List configured AI providers |
| POST | `/api/v1/ai/providers` | Add an AI provider configuration |
| PATCH | `/api/v1/ai/providers/{id}` | Update a provider configuration |
| DELETE | `/api/v1/ai/providers/{id}` | Remove a provider configuration |
| POST | `/api/v1/ai/providers/{id}/activate` | Set the active provider (by task scope) |
| GET | `/api/v1/ai/providers/{id}/health` | Check connectivity to a provider |

### Search

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/search` | Full-text search across parts, stock, projects, and documents |

Query parameters: `q` (query string), `type` (optional filter: `parts`, `stock`, `projects`, `documents`), `limit`, `offset`

### Admin

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/admin/health` | Application health check |
| GET | `/api/v1/admin/jobs` | List background enrichment jobs |
| GET | `/api/v1/admin/jobs/{id}` | Get a specific job's status |

### Import / Export  *(Epic 13)*

| Method | Path | Description |
|---|---|---|
| GET | `/api/import-export/parts/export` | Download all parts as a UTF-8 CSV file |
| GET | `/api/import-export/parts/template` | Download a blank parts import CSV template |
| POST | `/api/import-export/parts/import` | Upload a CSV file to bulk-create parts (existing `part_code` rows are skipped) |
| GET | `/api/import-export/stock/export` | Download all stock items as a UTF-8 CSV file |
| GET | `/api/import-export/stock/template` | Download a blank stock import CSV template |
| POST | `/api/import-export/stock/import` | Upload a CSV file to bulk-create stock items |

**Import response body:**
```json
{
  "created": 10,
  "skipped": 2,
  "errors": ["Row 5 (P-003): location 'Unknown' not found — skipped."]
}
```

**Duplicate detection:**

| Method | Path | Description |
|---|---|---|
| GET | `/api/parts/duplicates` | Return groups of parts that share the same normalised name or manufacturer part number |

**Bulk stock relocation:**

| Method | Path | Description |
|---|---|---|
| POST | `/api/stock/bulk-move` | Move a list of stock items to a new location or container |

`bulk-move` request body:
```json
{
  "stock_item_ids": ["uuid1", "uuid2"],
  "location_id": "uuid-of-destination-location"
}
```
Provide either `location_id` or `container_id`, not both.

---

## Background job endpoints

The worker process does not expose HTTP endpoints directly. Jobs are dispatched by the API and polled via the admin jobs endpoints above. The worker and API share access to the task queue and database.

---

### Part intake *(Epic 14)*

| Method | Path | Description |
|---|---|---|
| POST | `/api/parts/intake` | Accept a free-text part description; return candidate matching parts ranked by confidence and a suggested new part code |
| POST | `/api/parts/intake/apply` | Apply an intake decision: create a new part from a suggestion or add stock to an existing part |
| GET | `/api/parts/intake/{id}` | Get a previously saved `IntakeSuggestion` record |
| GET | `/api/parts/intake` | List recent intake suggestions |

**Intake request body:**
```json
{
  "description": "10k resistor 0603"
}
```

**Intake response body:**
```json
{
  "suggestion_id": "uuid",
  "normalised_text": "10k resistor 0603",
  "suggested_part_code": "RES-10K-0603-001",
  "candidates": [
    { "part_id": "uuid", "name": "10kΩ 0603 Resistor", "score": 0.92 }
  ],
  "suggested_placement": { "container_id": "uuid", "container_name": "Drawer 3" }
}
```

---

### Inventory hygiene *(Epic 15)*

| Method | Path | Description |
|---|---|---|
| GET | `/api/hygiene/summary` | Return a dashboard summary of inventory health issues |
| GET | `/api/hygiene/split-stock` | List parts whose stock is spread across multiple locations |
| GET | `/api/hygiene/needs-review` | List parts flagged `needs_review = true` |
| GET | `/api/hygiene/weak-metadata` | List parts missing documents, aliases, or capabilities |
| POST | `/api/parts/{id}/merge` | Merge a duplicate part into this part; stock items, aliases, and documents are moved; the duplicate is deleted |

**Hygiene summary response body:**
```json
{
  "duplicate_candidates": 3,
  "split_stock_parts": 5,
  "needs_review": 12,
  "no_documents": 47,
  "no_aliases": 31,
  "no_capabilities": 28,
  "missing_placement": 0
}
```

**Merge request body:**
```json
{
  "source_part_id": "uuid-of-part-to-absorb-and-delete"
}
```

---

### Backups *(Epic 16)*

| Method | Path | Description |
|---|---|---|
| GET | `/api/backups` | List backup records (most recent first) |
| POST | `/api/backups` | Create a backup record (used by backup scripts to register a completed backup) |
| GET | `/api/backups/latest` | Get the most recent completed backup of each type |
| GET | `/api/backups/{id}` | Get a specific backup record |
| POST | `/api/backups/trigger` | Request that the worker performs a backup now |

**Backup record body:**
```json
{
  "backup_type": "full",
  "triggered_by": "scheduled",
  "status": "completed",
  "started_at": "2026-04-14T02:00:00Z",
  "completed_at": "2026-04-14T02:01:23Z",
  "db_snapshot_path": "backups/db-20260414.tar.gz",
  "documents_snapshot_path": "backups/docs-20260414.tar.gz",
  "size_bytes": 204800
}
```

---

## Notes

- Pagination: list endpoints should support `limit` and `offset` (or cursor-based pagination — TBD)
- Filtering: list endpoints should support common filter query parameters where useful
- Error responses: standard JSON error body `{ "detail": "..." }` following FastAPI conventions
- All timestamps are returned in ISO 8601 UTC format
