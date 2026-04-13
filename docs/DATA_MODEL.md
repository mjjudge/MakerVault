# Data Model

> **Status:** Conceptual. No ORM or migration code exists yet. Field lists are indicative, not exhaustive.

This document describes the core entities in MakerVault and their relationships. The goal is to ensure all contributors share a common understanding of the domain before any database schema is written.

---

## Modelling principles

MakerVault separates five fundamental concerns:

| Concern | Entity |
|---|---|
| *What a thing is* | **Part** |
| *What you physically own* | **StockItem** |
| *Where it is* | **Location** |
| *What contains it* | **Container** |
| *What documents describe it* | **Document** (via join tables) |
| *What projects use it* | **Project** / **ProjectPart** |

This clean separation is the foundation that makes search, BOM generation, AI grounding, duplicate detection, and "where is it?" queries tractable. **Do not collapse these concerns into a single vague "item" table.**

---

## Entity overview

```
Category ──< Part ──< StockItem >──┬── Container ──> Location
               │           │       └── Location
               │           └──< UsageHistory
               │           └──< StockItemDocument >── Document
               │
               ├──< PartDocument >── Document
               ├──< PartAlias
               ├──< Capability
               └──< ProjectPart >── Project ──< ProjectDocument >── Document
                                        └──< UsageHistory

AIProviderConfig ──< EnrichmentJob
```

---

## Core entities

### Category

A **Category** provides a hierarchical taxonomy for Parts. Categories are stored in a separate table (not hard-coded as an enum) so they can grow over time.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | text | Display name (e.g. "Sensors", "Temperature") |
| `parent_category_id` | UUID | Self-reference for nested categories (nullable) |
| `description` | text | Optional description |
| `sort_order` | integer | Optional display ordering |

Example category tree: Sensors → Temperature, Sensors → Motion, Actuators, Microcontrollers, Single-board Computers, Power, Tools, Consumables.

---

### Part

A **Part** is the canonical definition of a type of component, board, module, tool, or device. It describes *what something is* in the abstract — not a specific physical unit you own.

> **A Part is not "the ESP32 in Box B." A Part is "ESP32 DevKit V1" as a type.**

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `part_code` | text | Internal unique code (unique across all Parts) |
| `name` | text | Common name (e.g. "ESP32 DevKit V1") |
| `short_description` | text | One-line summary |
| `long_description` | text | Extended free-text description |
| `category_id` | UUID | Foreign key → Category |
| `part_kind` | enum | See *Part kind* below |
| `manufacturer` | text | Manufacturer name |
| `manufacturer_part_number` | text | MPN |
| `default_unit` | text | e.g. "pcs", "ml", "m" |
| `package_type` | text | e.g. "DIP-8", "SOT-23", "through-hole" |
| `spec_summary` | text | Key specifications as a short text block |
| `capabilities_json` | jsonb | Structured capability data (extensible) |
| `tags` | text[] | Searchable tags (e.g. "I2C", "WiFi", "3.3V") |
| `aliases` | text[] | Denormalised search/cache field derived from PartAlias; not the primary source of alias truth |
| `search_text` | tsvector | Denormalised full-text search column |
| `is_consumable` | boolean | Whether this part is consumed on use |
| `is_serialised` | boolean | Whether individual units carry serial numbers |
| `is_hazardous` | boolean | Whether special handling is required |
| `is_active` | boolean | Whether this part is in active use |
| `status` | enum | `active`, `draft`, `archived` |
| `identification_confidence` | integer | 0–100; how certain the identification is |
| `needs_review` | boolean | Flagged for human review (e.g. AI-created record) |
| `provenance` | text | How this record was created (e.g. "manual", "ai_enriched", "imported") |
| `notes` | text | Free-text notes |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last update timestamp |

**Part kind** (enum): `component`, `board`, `module`, `device`, `tool`, `consumable`, `material`, `accessory`, `cable`, `power_supply`, `enclosure`.

---

### StockItem

A **StockItem** is what you physically own. One Part can have many StockItems — for example, three ESP32 boards in different locations, or a bag of 40 LEDs counted as one row with `quantity = 40`.

> **A StockItem is not the part definition. It is the physical instance (or grouped batch) in your possession.**

`stock_type` controls whether this item is tracked individually or as bulk stock:

- `serialised` — one unit with its own serial number
- `batch` — a specific batch/lot
- `bulk` — loose stock counted by quantity
- `consumable` — use-and-replace material
- `kit` — a grouped set

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `part_id` | UUID | Foreign key → Part |
| `stock_type` | enum | `serialised`, `batch`, `bulk`, `consumable`, `kit` |
| `quantity` | numeric | Number of units |
| `unit` | text | Unit of measure (overrides Part default if set) |
| `condition` | enum | `new`, `used`, `tested`, `untested`, `faulty`, `damaged`, `unknown` |
| `location_id` | UUID | Foreign key → Location (nullable if container is set; see *Placement rule* below) |
| `container_id` | UUID | Foreign key → Container (nullable if location is set; see *Placement rule* below) |
| `status` | enum | `available`, `reserved`, `consumed`, `missing`, `damaged`, `unknown` |
| `owner_label` | text | Optional human label (e.g. "From kit", "Work spare") |
| `serial_number` | text | Serial number (for `serialised` items) |
| `batch_number` | text | Batch number |
| `lot_number` | text | Lot number |
| `purchase_date` | date | Date purchased |
| `purchase_price` | numeric | Price paid |
| `supplier` | text | Supplier name |
| `supplier_order_ref` | text | Order or invoice reference |
| `expiry_date` | date | For perishable or time-limited items |
| `received_date` | date | Date received |
| `opened_date` | date | Date first opened (for consumables) |
| `photo_url` | text | URL/path to a photo of this specific item |
| `reserved_for_project_id` | UUID | Foreign key → Project (nullable) |
| `notes` | text | Free-text notes |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last update timestamp |

> **Placement rule:** A StockItem should always have a resolvable physical placement. Direct placement uses `location_id`; nested placement uses `container_id` (from which location can be derived through the container chain). A StockItem with neither field set is only valid when its `status` explicitly marks it as unplaced (e.g. `missing` or `unknown`). Unplaced stock must not occur accidentally — it must result from an explicit workflow action.

---

### Location

A **Location** is a physical place. Locations are hierarchical (a room inside a building, a building on a site).

> **A Location is the place, not the box or tray.** Boxes and trays are Containers.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | text | Display name (e.g. "Garage") |
| `location_type` | enum | `site`, `building`, `room`, `storage_area` |
| `parent_location_id` | UUID | Self-reference for nested locations (nullable) |
| `path` | text | Materialised path for efficient subtree queries (e.g. "Home/Garage") |
| `description` | text | Optional description |
| `notes` | text | Free-text notes |
| `is_active` | boolean | Whether this location is currently in use |

---

### Container

A **Container** is a storage object within a location — a box, tray, drawer, case, organiser, bag, shelf, or bin. Containers can nest inside other containers.

> **A Container belongs to a Location, or to another Container.** This models "Garage → Case F → Tray 2" correctly.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | text | Display name (e.g. "Box B", "Tray 4") |
| `container_type` | enum | `box`, `tray`, `drawer`, `case`, `organiser`, `bag`, `shelf`, `bin` |
| `location_id` | UUID | Foreign key → Location (top-level placement) |
| `parent_container_id` | UUID | Self-reference for nested containers (nullable) |
| `label_code` | text | Physical label code or barcode for scanning (unique when present) |
| `description` | text | Optional description |
| `notes` | text | Free-text notes |
| `is_active` | boolean | Whether this container is in use |
| `path` | text | Materialised path for efficient subtree queries (e.g. "Garage/Case F/Tray 2"); derived and cached, not manually set |

---

### Document

A **Document** is any locally preserved reference material: a PDF datasheet, pinout image, manual, saved vendor page, receipt, wiring note, or setup guide.

> **Documents are first-class entities, not simple file attachments.** They carry rich metadata, extracted text, and summaries that make them valuable for AI grounding and search.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `document_type` | enum | See *Document type* below |
| `title` | text | Human-readable title |
| `source_url` | text | Original upstream URL (nullable; may be dead) |
| `source_type` | enum | `uploaded`, `captured_from_web`, `manual_note`, `generated_summary` |
| `local_path` | text | Path on the document volume (relative to document root) |
| `mime_type` | text | MIME type of the stored file |
| `checksum` | text | SHA-256 of the stored file for integrity checking |
| `file_size_bytes` | bigint | File size |
| `captured_at` | timestamptz | When the document was captured or uploaded |
| `version_label` | text | Optional version label (e.g. "Rev C", "2023-10") |
| `text_extracted` | text | Raw text extracted from the document (for full-text search) |
| `summary` | text | AI-generated or manually written summary |
| `metadata_json` | jsonb | Extensible extracted metadata |
| `notes` | text | Free-text notes |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last update timestamp |

**Document type** (enum): `datasheet`, `manual`, `pinout`, `schematic`, `vendor_page`, `receipt`, `photo`, `project_note`, `setup_note`, `firmware_note`.

Documents do not have a hard foreign key to Part or Project. They are linked via join tables so that one Document can relate to multiple entities.

---

### ProjectDocument

Links Documents to Projects (e.g. wiring notes, project photos, setup instructions, design sketches, AI-generated plans).

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `project_id` | UUID | Foreign key → Project |
| `document_id` | UUID | Foreign key → Document |
| `relationship_type` | enum | `wiring_note`, `photo`, `setup_instruction`, `design_sketch`, `ai_plan`, `reference`, `other` |
| `notes` | text | Optional notes on the relationship |

---

### PartDocument

Links Documents to Parts.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `part_id` | UUID | Foreign key → Part |
| `document_id` | UUID | Foreign key → Document |
| `relationship_type` | enum | `primary_datasheet`, `manual`, `pinout`, `schematic`, `supporting_reference`, `other` |
| `is_primary` | boolean | Whether this is the primary document of its type for this part |
| `notes` | text | Optional notes on the relationship |

---

### StockItemDocument

Links Documents to StockItems (e.g. receipts, condition photos, serial number snapshots).

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `stock_item_id` | UUID | Foreign key → StockItem |
| `document_id` | UUID | Foreign key → Document |
| `relationship_type` | text | e.g. `receipt`, `condition_photo`, `serial_photo`, `other` |

---

### Project

A **Project** is a planned, active, or completed build or experiment.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | text | Project name |
| `slug` | text | URL-friendly identifier |
| `description` | text | Summary of the project |
| `status` | enum | `idea`, `planned`, `active`, `paused`, `completed`, `abandoned` |
| `goal` | text | What the project is trying to achieve |
| `difficulty` | enum | `beginner`, `intermediate`, `advanced` |
| `estimated_hours` | numeric | Rough time estimate |
| `priority` | integer | Sort priority |
| `notes` | text | Free-text notes |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last update timestamp |

---

### ProjectPart (BOM entry)

A **ProjectPart** links a Part to a Project, forming a bill of materials (BOM).

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `project_id` | UUID | Foreign key → Project |
| `part_id` | UUID | Foreign key → Part |
| `quantity_required` | numeric | Number of units needed |
| `unit` | text | Unit of measure |
| `is_optional` | boolean | Whether this part is optional for the project |
| `is_owned` | boolean | Derived/cache field — whether the required quantity is currently in stock; do not treat as authoritative. Recompute from StockItem availability. |
| `role` | enum | `controller`, `sensor`, `actuator`, `power`, `mounting`, `enclosure`, `other` |
| `notes` | text | Free-text notes |

---

### UsageHistory

Tracks what was actually used, consumed, moved, or tested.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `project_id` | UUID | Foreign key → Project (nullable) |
| `stock_item_id` | UUID | Foreign key → StockItem (nullable) |
| `part_id` | UUID | Foreign key → Part (nullable; denormalised for queries) |
| `action_type` | enum | `allocated`, `used`, `returned`, `consumed`, `tested`, `damaged` |
| `quantity_delta` | numeric | Change in quantity (negative for consumption) |
| `used_at` | timestamptz | When the event occurred |
| `notes` | text | Free-text notes |

---

### PartAlias

Stores alternate names, common nicknames, OCR-extracted labels, and AI-suggested aliases for a Part. Kept as a separate table (not embedded in JSON) to enable efficient fuzzy search.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `part_id` | UUID | Foreign key → Part |
| `alias` | text | The alternate name or search term |
| `alias_type` | enum | `common_name`, `manufacturer_name`, `nickname`, `ocr_extracted`, `ai_suggested` |
| `source` | text | Where this alias came from (e.g. "user", "ai_enrichment") |
| `is_preferred` | boolean | Whether this is the preferred display alias |

---

### Capability

Stores normalised capability/specification data for a Part. Provides structured data for AI-grounded queries ("show me 3.3V boards", "find any I2C sensors").

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `part_id` | UUID | Foreign key → Part |
| `capability_type` | enum | See *Capability type* below |
| `value_text` | text | Text value (e.g. "I2C") |
| `value_number` | numeric | Numeric value (e.g. 3.3) |
| `unit` | text | Unit for numeric value (e.g. "V", "mA") |
| `value_json` | jsonb | Extensible structured value |
| `source_document_id` | UUID | Foreign key → Document (nullable; where this was extracted from) |
| `confidence` | integer | 0–100; how confident the data is |

**Capability type** (enum): `voltage_min`, `voltage_max`, `logic_level`, `interface`, `wireless_protocol`, `current_draw`, `gpio_count`, `temperature_range`, `form_factor`.

---

### AIProviderConfig

Stores configuration for each configured AI provider. Secrets (API keys) are stored in environment variables; this table stores non-secret configuration only.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | text | Human label (e.g. "Local Ollama", "OpenAI GPT-4o") |
| `provider_type` | enum | `openai`, `anthropic`, `ollama`, `openai_compatible`, `local_custom` |
| `base_url` | text | Base URL for the provider's API |
| `model_name` | text | Model identifier (e.g. "gpt-4o", "llama3") |
| `task_scope` | enum | `chat`, `enrichment`, `embeddings`, `classification`, `project_ideas` |

> **Note:** `task_scope` is currently a single-value enum. If one provider configuration needs to support multiple task types cleanly, this field may evolve into a join table in a future migration.
| `is_enabled` | boolean | Whether this provider is enabled |
| `priority` | integer | Selection priority when multiple providers support the same scope |
| `config_json` | jsonb | Additional non-secret configuration |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last update timestamp |

---

### EnrichmentJob

Tracks background AI and parsing jobs. Records input, output, and status for traceability and retry.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `job_type` | enum | `extract_metadata`, `summarise_document`, `classify_part`, `generate_aliases`, `suggest_projects`, `embed_document` |
| `target_type` | text | Entity type being processed (e.g. "Part", "Document") |
| `target_id` | UUID | ID of the target entity |
| `provider_config_id` | UUID | Foreign key → AIProviderConfig (nullable) |
| `status` | enum | `queued`, `running`, `completed`, `failed`, `cancelled` |
| `input_hash` | text | Hash of the input used (for deduplication and re-run detection) |
| `result_json` | jsonb | Full structured result from the job |
| `error_message` | text | Error detail if failed |
| `started_at` | timestamptz | When the job started |
| `completed_at` | timestamptz | When the job finished (nullable) |
| `created_at` | timestamptz | Record creation timestamp |

---

## Relationships overview

```
Category     1──N  Part
Part         1──N  StockItem
Part         N──N  Document            (via PartDocument)
Part         N──N  Project             (via ProjectPart)
Part         1──N  PartAlias
Part         1──N  Capability
Location     1──N  Container
Location     1──N  StockItem           (direct placement, no container)
Container    1──N  Container           (nested containers)
Container    1──N  StockItem
StockItem    N──N  Document            (via StockItemDocument)
StockItem    1──N  UsageHistory
Project      1──N  UsageHistory
Project      N──N  Document            (via ProjectDocument)
AIProviderConfig  1──N  EnrichmentJob
```

---

## Key distinctions

### Part vs StockItem

This is the most important separation in the model.

| Concept | Entity | Example |
|---|---|---|
| The abstract type | Part | ESP32 DevKit V1 |
| A physical instance you own | StockItem | 3 units, Box B, Garage |

**Do not merge these.** A single Part definition may have many StockItems — units in different locations, in different conditions, with different purchase histories. Merging them collapses search, BOM generation, and duplicate detection.

### Location vs Container

| Concept | Entity | Example |
|---|---|---|
| The physical place | Location | Garage |
| The storage object in that place | Container | Case F, Tray 2 |

Containers belong to a Location (or to another Container). This models `Garage → Case F → Tray 2` correctly. Storing location as a text field loses the ability to move a whole case, search by room, or generate labels for nested containers.

### Document as a first-class entity

Documents are not simple file attachments. They carry extracted text, AI summaries, checksums, and source metadata. A Document can be linked to a Part, a StockItem, a Project, or none — via join tables. This makes stored documents a searchable, AI-grounded knowledge base rather than a dead file drop.

### AI suggestions must be traceable

Every AI-generated suggestion, enrichment result, or capability inference must point back to a grounded record (`part_id`, `stock_item_id`, `document_id`, or `project_id`). The database is the source of truth; AI is reasoning on top of it.

---

## v1 scope vs later extensions

### Minimum viable schema (Phase 1–2)

Implement these entities first:

- Part
- StockItem
- Location
- Container
- Category
- Document
- PartDocument
- StockItemDocument
- ProjectDocument
- Project
- ProjectPart

### Phase 3–4 additions

Add when implementing AI workflows:

- AIProviderConfig
- EnrichmentJob

### Phase 4–5 additions

Add when workflows and search mature:

- UsageHistory
- PartAlias
- Capability

---

---

## Likely uniqueness rules

These are not yet enforced as database constraints, but should be treated as identity rules during design and migration planning:

- `Part.part_code` — unique across all Parts
- `Project.slug` — unique across all Projects
- `Container.label_code` — unique when present (two containers must not share a scan code)
- `(PartAlias.part_id, PartAlias.alias)` — composite unique (no duplicate alias text per part)
- `Document.checksum` — candidates for checksum-based duplicate detection; two documents with the same SHA-256 may be the same file

---

## Quantities and units

Quantity and unit handling must support both countable items (pcs) and measured stock (ml, m, g). `Part.default_unit` provides the default unit for a part type; `StockItem.unit` allows a per-instance override (e.g. a reel of wire recorded in metres rather than pieces). Reporting and BOM calculations must respect the active unit on each row and must not assume all quantities are dimensionless integers.

---

## Indicative status enumerations

| Entity | Status values |
|---|---|
| Part | `active`, `draft`, `archived` |
| StockItem | `available`, `reserved`, `consumed`, `missing`, `damaged`, `unknown` |
| Project | `idea`, `planned`, `active`, `paused`, `completed`, `abandoned` |
| Document source type | `uploaded`, `captured_from_web`, `manual_note`, `generated_summary` |
| EnrichmentJob | `queued`, `running`, `completed`, `failed`, `cancelled` |
