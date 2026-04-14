# MakerVault — How-To Guide

This guide walks you through the recommended workflow for setting up and using
MakerVault as your self-hosted inventory system.

---

## Getting started

### 1. Start the stack

```bash
cd infra/docker
cp .env.example .env      # fill in any custom values
docker compose up -d
```

The web interface is available at `http://localhost` (or whatever host you
configured). The API documentation lives at `http://localhost/api/docs`.

---

## Setting up your physical storage

### 2. Add locations

A **Location** is a physical place — a room, a building, or a site. Go to
**Locations** in the navigation bar and click **+ New Location**. Give it a
descriptive name such as "Workshop" or "Bedroom Shelf".

### 3. Add containers

A **Container** is a storage object inside a location — a box, tray, drawer,
or cabinet. From the Locations page, click into a location and add containers.
Containers can be nested: a "Cabinet A" can contain "Drawer 1", "Drawer 2", etc.

Every container has an optional **Label Code** field. Use this to write or print
a short code on the physical container (e.g. "GA-BOX-01") so you can find the
right bin without opening the inventory system.

---

## Building your parts catalogue

### 4. Add parts

Go to **Parts** and click **+ New Part**. Fill in at minimum:

- **Part Code** — your internal identifier (e.g. `RES-10K-0603`)
- **Name** — a human-readable name (e.g. "10kΩ 0603 Resistor")

Other useful fields:

| Field | Purpose |
|---|---|
| Manufacturer / MPN | Makes parts searchable by manufacturer reference |
| Part Kind | Categorises the part (passive, IC, connector, etc.) |
| Tags | Free-form labels for filtering (e.g. `smd,resistor`) |
| Notes | Anything that doesn't fit elsewhere |

### 5. Attach documents

From a part's detail page, scroll to the **Documents** section. You can:

- Upload a PDF datasheet, pinout image, or any other file
- Paste a URL to record the original source (MakerVault stores a local copy)

Documents are stored on the Docker volume and are never lost if the external
URL goes away.

### 6. Add aliases

If a part is also known by other names or part numbers (e.g. "ESP-WROOM-32"
for an ESP32 board), add them in the **Aliases** panel. Aliases make the part
findable under any of its names in the global search bar.

---

## Tracking physical stock

### 7. Record stock items

Each physical batch of a part is a **Stock Item**. From a part's detail page,
click **+ Add Stock Item** and fill in:

- **Quantity** and **Unit** (pcs, metres, kg, …)
- **Location** or **Container** — exactly one is required
- Optional: condition, purchase date, price, supplier, serial number

### 8. Move stock

To move a single item, open the stock item and update its location/container.

To move multiple items at once use the **Bulk Move** API endpoint:

```
POST /api/stock/bulk-move
{
  "stock_item_ids": ["uuid1", "uuid2", ...],
  "location_id": "destination-location-uuid"
}
```

This moves all listed items atomically and reports any IDs that couldn't be
found.

---

## Projects and Bill of Materials

### 9. Create a project

Go to **Projects** and click **+ New Project**. Give it a name and an optional
description and status.

### 10. Build a BOM

From the project detail page, click **+ Add Part to BOM**, search for a part by
name or code, set the required quantity, and click Add.

The **BOM Availability** banner at the top of the project page updates in real
time to show whether you have enough stock for every part.

---

## AI features (optional)

### 11. Configure an AI provider

Go to **AI Settings** and click **+ Add Provider**. MakerVault supports:

| Provider type | When to use |
|---|---|
| **Ollama** | Fully local AI — no internet, no API key, runs on your host |
| **OpenAI** | Cloud-based GPT models — requires an API key |
| **OpenAI-compatible** | Any endpoint that speaks the OpenAI API (LM Studio, etc.) |

The API key is never stored in the database — only the environment variable
*name* is stored. Set the actual key in your `.env` file:

```
OPENAI_API_KEY=sk-...
```

### 12. Enrich a part

Open a part that has a datasheet attached. Click **Run Enrichment** in the
Enrichment panel to send the document text to your AI provider for analysis.
The AI will suggest:

- A short description
- Capabilities (voltage range, current, frequency, etc.)
- Tags
- Aliases

Review and apply or dismiss each suggestion. Nothing is saved without your
confirmation.

### 13. Get project inspiration

Go to **Inspire** and describe what you want to build. MakerVault sends your
current inventory to the AI and asks for project ideas that make use of the
parts you already own. The response shows which parts are in stock and which
are missing.

---

## Bulk import

### 14. Import parts from a spreadsheet

1. Go to **Import / Export** and download the **parts template**.
2. Open the template in Excel or Google Sheets and fill in your parts.
3. Save the file as "CSV UTF-8".
4. Upload the file on the Import / Export page.

Rules:

- `part_code` and `name` are required; all other columns are optional.
- If a `part_code` already exists, that row is **skipped** (never overwritten).
- Boolean columns (`is_consumable`, etc.) accept `true`/`false`, `1`/`0`,
  or `yes`/`no`.
- Tags are comma-separated in a single cell: `microcontroller,wifi,smd`.

### 15. Import stock from a spreadsheet

1. Download the **stock template**.
2. Fill in at minimum `part_code` and either `location_name` or `container_name`
   (but not both).
3. Quantities default to `1` if left blank.
4. Upload on the Import / Export page.

The parts and locations/containers referenced in the CSV must already exist
before importing stock.

---

## Exporting and backup

### 16. Export to CSV

Click **Export parts CSV** or **Export stock CSV** on the Import / Export page.
These downloads give you a point-in-time snapshot of your entire catalogue and
stock in a format readable by any spreadsheet application.

### 17. Back up the database and document store

MakerVault stores all data in two places:

1. **PostgreSQL database** — the `db` Docker volume
2. **Document store** — the `documents` Docker volume

To create a full backup:

```bash
# Stop the stack to ensure a consistent snapshot (optional but recommended)
docker compose stop

# Back up the Postgres volume
docker run --rm \
  -v makervault_db_data:/source:ro \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/db-$(date +%Y%m%d).tar.gz -C /source .

# Back up the document store
docker run --rm \
  -v makervault_documents:/source:ro \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/docs-$(date +%Y%m%d).tar.gz -C /source .

# Restart
docker compose start
```

Store backups off-device. A weekly automated snapshot plus the CSV export after
significant changes is a practical strategy for a single-user system.

---

## Finding potential duplicates

Go to the API docs (`/api/docs`) and call `GET /api/parts/duplicates` to get a
list of part groups that share the same name or manufacturer part number. Review
each group and either merge them (currently a manual process) or rename one to
make them distinct.

---

## Tips

- Use the **global search bar** on the Home page to find any part by name, code,
  manufacturer, MPN, or alias.
- The **Documents** page lets you search and filter all uploaded files across the
  entire system.
- The **History** page lets you record and review stock usage events linked to
  projects.
- The **API docs** at `/api/docs` (FastAPI Swagger UI) let you explore and test
  every endpoint interactively.
