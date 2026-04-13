# MakerVault — UI Screenshots

This document captures key screens of the MakerVault web interface.
Screenshots were taken against a live development stack (FastAPI + React + PostgreSQL).

---

## 1. Home / Search

**URL:** `/`

The landing page shows inventory statistics at a glance (parts count, stock items, locations),
a global part-search bar, and quick-access links to the main sections.

![Home page](https://github.com/user-attachments/assets/0ef25202-6f93-4523-9bf4-1c7dbd433aa2)

---

## 2. Parts List

**URL:** `/parts`

Tabular view of all parts with columns for Part Code (linked to detail), Name, Kind, Manufacturer,
Default Unit, and Status badge. Includes a live search bar (searches name, code, manufacturer, and
aliases) and a "+ New Part" modal trigger.

![Parts list](https://github.com/user-attachments/assets/77b2470c-68b6-4651-bedb-150e3cc54aae)

---

## 3. Part Detail

**URL:** `/parts/:id`

Detailed view for a single part. Shows all metadata fields (status, kind, description,
manufacturer, MPN, package, spec, tags, notes), the current stock items for that part
with resolved placement names, an attached-documents section with an upload/link workflow,
and an **Aliases** management panel where alternate names can be added or removed.

![Part detail — ESP32 DevKit V1](https://github.com/user-attachments/assets/98c93ce8-eff1-4366-b13c-62bdb3589e45)

---

## 4. Projects List

**URL:** `/projects`

List of all projects with Name, Description, Status badge (active / on hold / completed /
archived), and creation date. Includes a full-text search bar and "+ New Project" modal.

![Projects list](https://github.com/user-attachments/assets/b90ad553-66a9-470c-909d-efe5516fbc5f)

---

## 5. Project Detail — BOM & Availability

**URL:** `/projects/:id`

Full project view introduced in Epic 7. Shows project metadata, a real-time **BOM
Availability** banner (green "All parts available" / red "Some parts short"), the Bill of
Materials table with per-part required-vs-in-stock quantities and availability tick/cross,
and a document attachment section.

![Project detail — ESP32 Weather Station](https://github.com/user-attachments/assets/2c8cbf23-ad8b-48c9-bb0f-0f4dd4feb0d7)

---

## 6. Add Part to BOM Dialog

**URL:** `/projects/:id` (modal)

Inline part-search autocomplete that filters the parts catalogue as you type, then lets you
set the required quantity, optional unit override, and notes before adding the entry to the
project BOM.

![Add Part to BOM dialog](https://github.com/user-attachments/assets/58ca7f1b-9f31-4da4-86d8-91656e4eaf05)

---

## 7. Part Aliases Panel (Epic 8)

**URL:** `/parts/:id` (lower section)

New in Epic 8 — each part now has an **Aliases** panel. Aliases are alternate names for
the part (e.g. "ESP-WROOM-32" for an ESP32 board). Adding an alias makes the part
discoverable by that term in the global search bar. Aliases can be added inline and removed
with a single click.

> Screenshot to be added after next deployment.

---

## 8. Stock Page — Resolved Placement Paths (Epic 8)

**URL:** `/stock`

New in Epic 8 — stock items now show the **resolved name** of their container or location
instead of raw UUID fragments. The Part column now shows the part name as a clickable link
to the part detail page.

> Screenshot to be added after next deployment.

---

## 9. AI Settings — Provider List (Epic 9)

**URL:** `/ai`

New in Epic 9 — a dedicated **AI Settings** page accessible from the global navigation bar.
Shows all configured AI providers with their type, model, and enabled/default status.
Includes a live **Test** button for each provider (health-check against the actual endpoint),
enable/disable toggle, "Set default" shortcut, and an edit/delete workflow.
A help panel at the bottom explains how API keys are managed via environment variables.

![AI Settings — empty state](https://github.com/user-attachments/assets/fc71958e-f2c7-4bfa-baba-a917b2ff1151)

---

## 10. AI Settings — Add Provider Modal (Epic 9)

**URL:** `/ai` (modal)

The **Add AI Provider** modal. Selecting a provider type auto-populates sensible defaults
(base URL for Ollama, model name, env var name for OpenAI). The `api_key_env_var` field
records the *name* of the environment variable holding the API key — the key itself is
never sent to or stored by the server.

![AI Settings — Add Provider modal](https://github.com/user-attachments/assets/ea21530f-3358-4acd-86ab-573a9a84c462)
