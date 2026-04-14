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

### 4. Add parts the smart way (assisted intake)

Go to **Parts** and click **+ Add Part**. You can fill in the form manually, or
use the **Smart Intake** field at the top of the form.

Type a plain-English description of what you are adding, for example:

- `10k resistor 0603`
- `ESP32 dev board`
- `DHT22 temperature sensor`

MakerVault will:

1. Search your existing catalogue for close matches and show you ranked
   candidates with confidence scores.
2. If nothing matches well enough, suggest a unique human-readable part code
   (e.g. `RES-10K-0603-001`).
3. Suggest a storage location or container based on where you have put similar
   parts in the past.

You then choose one of three actions:

| Action | What happens |
|---|---|
| **Use existing** | No new part is created. You are taken directly to the matched part to add a new stock item. |
| **Create new** | A new Part is created with the suggested code, pre-filled tags and aliases. |
| **Dismiss** | Nothing is saved. You can fill in the form manually. |

> **Nothing is created until you confirm.** Suggestions are advisory and require
> your explicit approval before any record is written.

### 5. Add parts manually

If you prefer to enter everything yourself, go to **Parts** and click
**+ New Part**. Fill in at minimum:

- **Part Code** — your internal identifier (e.g. `RES-10K-0603`)
- **Name** — a human-readable name (e.g. "10kΩ 0603 Resistor")

Other useful fields:

| Field | Purpose |
|---|---|
| Manufacturer / MPN | Makes parts searchable by manufacturer reference |
| Part Kind | Categorises the part (passive, IC, connector, etc.) |
| Tags | Free-form labels for filtering (e.g. `smd,resistor`) |
| Notes | Anything that doesn't fit elsewhere |

### 6. Attach documents

From a part's detail page, scroll to the **Documents** section. You can:

- Upload a PDF datasheet, pinout image, or any other file
- Paste a URL to record the original source (MakerVault stores a local copy)

Documents are stored on the Docker volume and are never lost if the external
URL goes away.

### 7. Add aliases

If a part is also known by other names or part numbers (e.g. "ESP-WROOM-32"
for an ESP32 board), add them in the **Aliases** panel. Aliases make the part
findable under any of its names in the global search bar.

---

## Tracking physical stock

### 8. Record stock items

Each physical batch of a part is a **Stock Item**. From a part's detail page,
click **+ Add Stock Item** and fill in:

- **Quantity** and **Unit** (pcs, metres, kg, …)
- **Location** or **Container** — exactly one is required
- Optional: condition, purchase date, price, supplier, serial number

### 9. Move stock

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

### 10. Create a project

Go to **Projects** and click **+ New Project**. Give it a name and an optional
description and status.

### 11. Build a BOM

From the project detail page, click **+ Add Part to BOM**, search for a part by
name or code, set the required quantity, and click Add.

The **BOM Availability** banner at the top of the project page updates in real
time to show whether you have enough stock for every part.

---

## AI features (optional)

### 12. Configure an AI provider

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

### 13. Enrich a part

Open a part that has a datasheet attached. Click **Run Enrichment** in the
Enrichment panel to send the document text to your AI provider for analysis.
The AI will suggest:

- A short description
- Capabilities (voltage range, current, frequency, etc.)
- Tags
- Aliases

Review and apply or dismiss each suggestion. Nothing is saved without your
confirmation.

### 14. Get project inspiration

Go to **Inspire** and describe what you want to build. MakerVault sends your
current inventory to the AI and asks for project ideas that make use of the
parts you already own. The response shows which parts are in stock and which
are missing.

---

## Bulk import

### 15. Import parts from a spreadsheet

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

### 16. Import stock from a spreadsheet

1. Download the **stock template**.
2. Fill in at minimum `part_code` and either `location_name` or `container_name`
   (but not both).
3. Quantities default to `1` if left blank.
4. Upload on the Import / Export page.

The parts and locations/containers referenced in the CSV must already exist
before importing stock.

---

## Exporting and backup

### 17. Export to CSV

Click **Export parts CSV** or **Export stock CSV** on the Import / Export page.
These downloads give you a point-in-time snapshot of your entire catalogue and
stock in a format readable by any spreadsheet application.

### 18. Back up the database and document store

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

### 19. Monitor backup status

Go to **Admin → Backup Status** to see when MakerVault was last successfully
backed up. The panel shows:

- Last full backup date and size
- Last database-only backup
- Last documents-only backup
- Any recorded failures with their error messages

Each time you run the backup script above, the script registers the result via
`POST /api/backups` so that the status page stays up to date. You can also
trigger a backup from the UI by clicking **Run Backup Now** — this enqueues a
worker job and updates the status once it completes.

If the "Last backup" date is more than a week old, the panel shows a warning.

---

## Keeping your inventory clean

### 20. Review the hygiene dashboard

Go to **Admin → Inventory Health** to see a summary of data quality issues:

| Issue | What it means |
|---|---|
| **Duplicate candidates** | Parts that share the same name or MPN — possible duplicates |
| **Split stock** | Parts with stock spread across multiple locations |
| **Needs review** | Parts flagged by an automated process for human attention |
| **No documents** | Parts with no datasheet, pinout, or other reference attached |
| **No aliases** | Parts with no alternate names or search terms |
| **No capabilities** | Parts with no structured spec data |

Click any category to drill into the affected parts.

### 21. Resolve duplicate parts

From the **Duplicate Candidates** list, review each group. When you are certain
two entries are the same component:

1. Open the part you want to keep.
2. Click **Merge into this part** and select the duplicate to absorb.
3. Confirm the merge.

MakerVault will move all stock items, aliases, capabilities, and document links
from the duplicate to the surviving part and then delete the duplicate. This
operation cannot be undone, so review carefully first.

### 22. Review split-stock

Parts listed on the **Split Stock** page have physical stock in more than one
location. This is sometimes intentional (one batch in the workshop, one in
storage). If it is not, use the bulk move endpoint or the per-item move button
to consolidate.

---

## Finding potential duplicates (quick path)

Go to the API docs (`/api/docs`) and call `GET /api/parts/duplicates` to get a
list of part groups that share the same name or manufacturer part number. Review
each group in the UI or use the merge workflow described above.

---

## Tips

- Use the **global search bar** on the Home page to find any part by name, code,
  manufacturer, MPN, or alias.
- The **Documents** page lets you search and filter all uploaded files across the
  entire system.
- The **History** page lets you record and review stock usage events linked to
  projects.
- The **Inventory Health** page surfaces data quality issues without requiring
  direct API access.
- The **API docs** at `/api/docs` (FastAPI Swagger UI) let you explore and test
  every endpoint interactively.
