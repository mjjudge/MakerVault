# API Specification

> **Status:** Draft direction only. No implementation exists. Endpoint signatures are indicative and subject to change.

---

## Approach

- REST-first API served by FastAPI
- All endpoints under `/api/v1/` prefix
- JSON request and response bodies
- Standard HTTP status codes
- OpenAPI documentation auto-generated at `/api/docs` (FastAPI default)
- Authentication: TBD — likely bearer token or session cookie for single-user deployment

---

## Resource groups

### Parts

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/parts` | List all parts (with pagination and filters) |
| POST | `/api/v1/parts` | Create a new part |
| GET | `/api/v1/parts/{id}` | Get a single part |
| PATCH | `/api/v1/parts/{id}` | Update a part |
| DELETE | `/api/v1/parts/{id}` | Delete a part |
| GET | `/api/v1/parts/{id}/stock` | List all stock items for a part |
| GET | `/api/v1/parts/{id}/documents` | List documents attached to a part |
| GET | `/api/v1/parts/{id}/projects` | List projects that use this part |

### Stock

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/stock` | List all stock items (with filters by part, location, container) |
| POST | `/api/v1/stock` | Create a stock item |
| GET | `/api/v1/stock/{id}` | Get a stock item |
| PATCH | `/api/v1/stock/{id}` | Update a stock item (quantity, condition, location) |
| DELETE | `/api/v1/stock/{id}` | Remove a stock item |
| POST | `/api/v1/stock/{id}/move` | Move a stock item to a different container |
| GET | `/api/v1/stock/{id}/history` | Get usage history for a stock item |

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
| GET | `/api/v1/ai/providers` | List configured AI providers |
| POST | `/api/v1/ai/providers` | Add an AI provider configuration |
| PATCH | `/api/v1/ai/providers/{id}` | Update a provider configuration |
| DELETE | `/api/v1/ai/providers/{id}` | Remove a provider configuration |
| POST | `/api/v1/ai/providers/{id}/activate` | Set the active provider |
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

---

## Background job endpoints

The worker process does not expose HTTP endpoints directly. Jobs are dispatched by the API and polled via the admin jobs endpoints above. The worker and API share access to the task queue and database.

---

## Notes

- Pagination: list endpoints should support `limit` and `offset` (or cursor-based pagination — TBD)
- Filtering: list endpoints should support common filter query parameters where useful
- Error responses: standard JSON error body `{ "detail": "..." }` following FastAPI conventions
- All timestamps are returned in ISO 8601 UTC format
