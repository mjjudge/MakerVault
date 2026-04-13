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
Default Unit, and Status badge. Includes a live search bar and a "+ New Part" modal trigger.

![Parts list](https://github.com/user-attachments/assets/77b2470c-68b6-4651-bedb-150e3cc54aae)

---

## 3. Part Detail

**URL:** `/parts/:id`

Detailed view for a single part. Shows all metadata fields (status, kind, description,
manufacturer, MPN, package, spec, notes), the current stock items for that part,
and an attached-documents section with an upload/link workflow.

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
