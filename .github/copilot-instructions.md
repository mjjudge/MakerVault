# GitHub Copilot Instructions

This file provides repository-specific guidance for GitHub Copilot interactions.

---

## What this project is

MakerVault is a self-hosted inventory and knowledge system for electronics and workshop parts. It combines inventory tracking, local document preservation, and pluggable AI assistance.

## Architecture at a glance

- **Backend:** FastAPI (Python) in `apps/api/`
- **Frontend:** React + Vite + TypeScript in `apps/web/`
- **Worker:** Python background jobs in `apps/worker/`
- **Database:** PostgreSQL (primary, relational, source of truth)
- **Document store:** Local filesystem volume
- **AI:** Pluggable provider abstraction — do not hard-code any single vendor
- **Deployment:** Docker Compose on Ubuntu

## Key documentation

- `docs/DATA_MODEL.md` — core entities and their fields
- `docs/ARCHITECTURE.md` — system components and data flows
- `docs/TECHNICAL_SPEC.md` — implementation direction and constraints
- `docs/DECISIONS.md` — architectural decisions made and options still open
- `docs/ROADMAP.md` — phased implementation plan
- `docs/API_SPEC.md` — draft API resource groups and endpoints
- `AGENTS.md` — rules for agents and automated contributors

## Behavioural guidelines

- **Do not guess.** If requirements or architecture are unclear, flag it rather than invent a solution.
- **Stay aligned with the docs.** If code diverges from documentation, update the docs.
- **Use Conventional Commits:** `feat(scope): description`, `fix(scope): description`, etc.
- **The database is the source of truth.** AI provider outputs are for enrichment and suggestion only.
- **Do not hard-code AI providers.** All AI calls must go through the provider abstraction layer.
- **No hidden dependencies.** Any new external service or library must be documented.
- **Prefer small, focused changes.** A clear, reviewable PR beats a large sweep.

## Current phase

Phase 0 (scaffold and documentation). No application business logic has been implemented yet. See `docs/ROADMAP.md` for the phased plan.
