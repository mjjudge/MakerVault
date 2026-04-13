# apps/api

> **Status:** Placeholder. No implementation yet.

This directory will contain the MakerVault FastAPI backend.

## Intended stack

- Python 3.12+
- FastAPI
- SQLAlchemy (async) + Alembic
- Pydantic v2

## Planned structure (to be created)

```
apps/api/
├── makervault/
│   ├── main.py          # FastAPI app entry point
│   ├── config.py        # Settings (from environment)
│   ├── database.py      # DB engine and session setup
│   ├── models/          # SQLAlchemy ORM models
│   ├── schemas/         # Pydantic request/response schemas
│   ├── routers/         # FastAPI route handlers
│   ├── services/        # Business logic
│   ├── ai/              # AI provider abstraction
│   └── documents/       # Document storage helpers
├── alembic/             # Alembic migration environment
├── tests/               # API tests
├── pyproject.toml
└── Dockerfile
```

## Getting started

See `scripts/bootstrap.sh` for environment setup.
