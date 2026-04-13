# Data Model

> **Status:** Conceptual. No ORM or migration code exists yet. Field lists are indicative, not exhaustive.

This document describes the core entities in MakerVault and their relationships. The goal is to ensure all contributors share a common understanding of the domain before any database schema is written.

---

## Entities overview

```
Part ──< StockItem >── Container ──> Location
 │            │
 │            └──< UsageHistory
 │
 └──< Document
 └──< ProjectPart >── Project
                         └──< Document

AIProviderConfig
EnrichmentJob
```

---

## Part

A **Part** is the definition of a type of component, board, tool, or device. It describes *what something is*, not a specific owned unit.

| Field | Description |
|---|---|
| `id` | UUID primary key |
| `name` | Common name (e.g. "ESP32-WROOM-32") |
| `manufacturer` | Manufacturer name |
| `mpn` | Manufacturer part number |
| `description` | Free-text description |
| `category` | e.g. microcontroller, sensor, passive, tool, consumable |
| `tags` | Array of searchable tags (e.g. "I2C", "WiFi", "3.3V") |
| `datasheet_url` | Original upstream URL (may be dead; local copy is in Document) |
| `notes` | Free-text notes |
| `created_at` | Timestamp |
| `updated_at` | Timestamp |

---

## StockItem

A **StockItem** represents one or more physical units of a Part that are actually owned. A single Part may have multiple StockItems (e.g. units in different locations, or units with different serial numbers).

| Field | Description |
|---|---|
| `id` | UUID primary key |
| `part_id` | Foreign key → Part |
| `container_id` | Foreign key → Container (nullable if location is approximate) |
| `quantity` | Number of units at this location |
| `serial_number` | Optional serial number for trackable devices |
| `condition` | e.g. new, used, faulty, untested |
| `purchase_date` | Date of purchase |
| `purchase_price` | Price paid (for reference) |
| `supplier` | Supplier name |
| `supplier_order_ref` | Order or invoice reference |
| `notes` | Free-text notes |
| `created_at` | Timestamp |
| `updated_at` | Timestamp |

---

## Location

A **Location** is a physical room or area (e.g. Loft, Garage, Office).

| Field | Description |
|---|---|
| `id` | UUID primary key |
| `name` | Display name (e.g. "Loft") |
| `description` | Optional description |
| `parent_id` | Optional self-reference for sub-locations |
| `created_at` | Timestamp |

---

## Container

A **Container** is a physical storage object within a location: a box, tray, drawer, case, shelf, organiser, or similar.

| Field | Description |
|---|---|
| `id` | UUID primary key |
| `name` | Display name (e.g. "Box B", "Blue Tray 4") |
| `location_id` | Foreign key → Location |
| `parent_container_id` | Optional self-reference for nested containers (e.g. a tray inside a case) |
| `description` | Optional description |
| `created_at` | Timestamp |

---

## Document

A **Document** is a locally preserved file or reference. It may be a PDF datasheet, a manual, a photo, a schematic, a receipt, a pinout image, a saved vendor page, or a plain-text note.

| Field | Description |
|---|---|
| `id` | UUID primary key |
| `title` | Human-readable title |
| `document_type` | e.g. datasheet, manual, schematic, pinout, receipt, note, vendor_page, photo |
| `file_path` | Path to the local file on disk (relative to document root) |
| `mime_type` | MIME type of the stored file |
| `original_url` | Source URL if captured from the web (nullable) |
| `part_id` | Foreign key → Part (nullable) |
| `project_id` | Foreign key → Project (nullable) |
| `notes` | Free-text notes |
| `created_at` | Timestamp |

---

## Project

A **Project** is a build, experiment, or planned activity. It may be completed, in progress, planned, or just an idea.

| Field | Description |
|---|---|
| `id` | UUID primary key |
| `name` | Project name |
| `description` | Summary of what the project does |
| `status` | e.g. idea, planned, in_progress, completed, abandoned |
| `notes` | Free-text notes |
| `created_at` | Timestamp |
| `updated_at` | Timestamp |

---

## ProjectPart (BOM item)

A **ProjectPart** links a Part to a Project, forming a bill of materials (BOM). It records the intended or actual use of a part within the project.

| Field | Description |
|---|---|
| `id` | UUID primary key |
| `project_id` | Foreign key → Project |
| `part_id` | Foreign key → Part |
| `quantity` | Number of units used or required |
| `role` | Description of the part's role in the project (e.g. "main MCU", "power switch") |
| `status` | e.g. planned, sourced, fitted, spare |
| `notes` | Free-text notes |

---

## UsageHistory

A **UsageHistory** record captures a point-in-time event where a StockItem was used, moved, or modified.

| Field | Description |
|---|---|
| `id` | UUID primary key |
| `stock_item_id` | Foreign key → StockItem |
| `project_id` | Foreign key → Project (nullable) |
| `event_type` | e.g. used, returned, moved, discarded, repaired |
| `quantity_delta` | Change in quantity (negative for consumption) |
| `notes` | Free-text notes |
| `event_at` | Timestamp of the event |
| `created_at` | Record creation timestamp |

---

## AIProviderConfig

Stores configuration for each configured AI provider. Secrets (API keys) are stored in environment variables; this table stores non-secret configuration.

| Field | Description |
|---|---|
| `id` | UUID primary key |
| `name` | Human label (e.g. "Local Ollama", "OpenAI GPT-4o") |
| `provider_type` | e.g. openai, anthropic, ollama, deepseek, openai_compatible |
| `endpoint_url` | Base URL for the provider's API |
| `model_name` | Model identifier (e.g. "gpt-4o", "llama3") |
| `is_active` | Boolean; whether this is the currently active provider |
| `supports_embeddings` | Boolean; whether this provider supports embedding generation |
| `notes` | Free-text notes |
| `created_at` | Timestamp |
| `updated_at` | Timestamp |

---

## EnrichmentJob

Tracks background AI enrichment tasks such as auto-filling part descriptions or extracting metadata from documents.

| Field | Description |
|---|---|
| `id` | UUID primary key |
| `job_type` | e.g. enrich_part, index_document, suggest_projects |
| `entity_type` | The entity type being enriched (e.g. "Part", "Document") |
| `entity_id` | ID of the entity |
| `provider_config_id` | Foreign key → AIProviderConfig |
| `status` | e.g. pending, running, completed, failed |
| `result_summary` | Short text summary of the outcome |
| `error_message` | Error detail if failed |
| `created_at` | Timestamp |
| `completed_at` | Timestamp (nullable) |

---

## Relationships summary

- A **Part** may have many **StockItems**, many **Documents**, and appear in many **ProjectParts**
- A **StockItem** belongs to one **Part** and optionally to one **Container**
- A **Container** belongs to one **Location** and may nest within another **Container**
- A **Project** may have many **ProjectParts** and many **Documents**
- A **Document** may be attached to a **Part** or a **Project** (or neither, as a free-standing reference)
- An **EnrichmentJob** is linked to a specific entity and a specific **AIProviderConfig**
