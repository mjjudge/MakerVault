# apps/worker

> **Status:** Placeholder. No implementation yet.

This directory will contain the MakerVault background worker process.

## Intended stack

- Python 3.12+
- Task queue: TBD (Celery + Redis or a simple DB-backed queue; see `docs/DECISIONS.md`)

## Responsibilities

- Document ingestion and processing
- AI enrichment jobs (triggered by the API, processed asynchronously)
- Background indexing tasks

## Planned structure (to be created)

```
apps/worker/
├── makervault_worker/
│   ├── main.py          # Worker entry point
│   ├── tasks/           # Task definitions
│   └── ai/              # Shared AI helpers (or imported from apps/api)
├── tests/
├── pyproject.toml
└── Dockerfile
```

## Getting started

See `scripts/bootstrap.sh` for environment setup.
