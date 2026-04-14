# MakerVault

MakerVault is a self-hosted inventory and knowledge system for electronics, IoT, workshop parts, tools, and technical reference material. It helps you track what you own, where it is stored, what it can do, which projects it has been used in, and what you could build with it. The system preserves important technical reference material locally and supports pluggable AI providers rather than hard-coding any single AI vendor.

> **Status:** Active development. Epics 0–12 complete. Core inventory, stock, locations, documents, projects, BOM, search refinement, AI provider abstraction, AI enrichment, AI project inspiration, and usage history tracking are all working. See [BACKLOG.md](BACKLOG.md) for the full roadmap.

---

## What's working

| Feature | Status |
|---|---|
| Parts catalogue (create, edit, search, delete) | ✅ |
| Stock items with physical placement | ✅ |
| Hierarchical locations and containers | ✅ |
| Document upload, storage, and linking to parts/stock/projects | ✅ |
| Projects and Bill of Materials with availability check | ✅ |
| Part aliases — alternate-name search | ✅ |
| Tag-based filtering | ✅ |
| Resolved placement paths in stock responses | ✅ |
| AI enrichment jobs (enrich parts and documents on demand) | ✅ |
| AI project inspiration — "what can I build with what I own?" | ✅ |
| Usage history — record allocation, consumption, returns, and damage events | ✅ |
| Stock quantity auto-updated from consumption/return events | ✅ |
| OpenAPI docs at `/api/docs` | ✅ |

---

## Screenshots

### Home / Search

![Home page](https://github.com/user-attachments/assets/0ef25202-6f93-4523-9bf4-1c7dbd433aa2)

### Part Detail — with aliases and tags

![Part detail — ESP32 DevKit V1](https://github.com/user-attachments/assets/98c93ce8-eff1-4366-b13c-62bdb3589e45)

### Project Detail — BOM & Availability

![Project detail — BOM availability](https://github.com/user-attachments/assets/2c8cbf23-ad8b-48c9-bb0f-0f4dd4feb0d7)

See [`docs/SCREENSHOTS.md`](docs/SCREENSHOTS.md) for the full screenshot gallery.

---

## Core goals

- Track parts, tools, boards, consumables, and devices with precise physical locations
- Distinguish between a part definition, a specific owned instance, a storage location, and a container
- Attach and preserve datasheets, manuals, pinouts, and notes locally
- Record serial numbers, condition, purchase details, and notes per device or unit
- Link parts to projects; record BOMs and usage history
- Support AI-assisted search, enrichment, and project suggestions grounded in actual inventory
- Support multiple AI providers including hosted and self-hosted models

## Non-goals (initial phase)

- Marketplace or supplier integrations
- Automatic ordering or procurement
- Multi-user enterprise workflows
- Advanced computer vision or part recognition
- Full CAD or schematic capture
- Complex permissions model
- Full mobile app
- Autonomous AI agents that modify inventory without user confirmation

## Running with Docker

Docker Compose is the primary way to run MakerVault. No local Python or Node.js installation is required.

```sh
# 1. Copy the example environment file and set required values
cp infra/docker/.env.example infra/docker/.env
#    Edit infra/docker/.env — set POSTGRES_PASSWORD and SECRET_KEY at minimum

# 2. Start all services
docker compose -f infra/docker/docker-compose.yml up

# Or, using the Makefile shortcut:
make up
```

Once running:

| Service | URL |
|---|---|
| Web UI | http://localhost |
| API | http://localhost/api *(proxied via nginx)* |
| API Docs | http://localhost/api/docs |

To stop: `docker compose -f infra/docker/docker-compose.yml down` or `make down`.

---

## Running tests

```sh
# Backend tests (Python — no PostgreSQL required; uses SQLite in-memory)
cd apps/api
pip install -e ".[dev]"
python -m pytest tests/ -v

# Frontend tests
cd apps/web
npm install
npm test
```

---

## Architecture

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python), containerised |
| Frontend | React + Vite + TypeScript, containerised |
| Database | PostgreSQL 16 (Docker, persistent volume) |
| Document store | Local filesystem volume (`/data/makervault/documents`) |
| Background jobs | Worker process (Python), containerised |
| AI abstraction | Pluggable provider layer — OpenAI, Ollama, OpenAI-compatible (Epic 9 ✅) |
| Reverse proxy | Nginx (Docker) |
| Deployment | Docker Compose on Ubuntu |

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for details.

## Repository structure

```
MakerVault/
├── README.md
├── AGENTS.md
├── BACKLOG.md
├── Makefile
├── .gitignore
├── .editorconfig
├── LICENSE
├── apps/
│   ├── api/          # FastAPI backend
│   │   ├── src/makervault/
│   │   │   ├── ai/         # AI provider abstraction (base, adapters, service)
│   │   │   ├── models/     # SQLAlchemy ORM models
│   │   │   ├── routers/    # FastAPI endpoint routers
│   │   │   ├── schemas/    # Pydantic request/response schemas
│   │   │   └── services/   # Business logic and file storage
│   │   ├── migrations/     # Alembic database migrations
│   │   └── tests/          # Pytest test suite
│   ├── web/          # React + Vite frontend
│   │   └── src/
│   │       ├── api/        # Typed API client
│   │       ├── pages/      # Route page components
│   │       └── components/ # Shared UI components
│   └── worker/       # Background job worker
├── docs/
│   ├── PRODUCT_VISION.md
│   ├── TECHNICAL_SPEC.md
│   ├── DATA_MODEL.md
│   ├── ARCHITECTURE.md
│   ├── ROADMAP.md
│   ├── API_SPEC.md
│   ├── UX_NOTES.md
│   ├── DECISIONS.md
│   └── SCREENSHOTS.md
├── infra/
│   ├── docker/       # Docker Compose and service configs
│   └── nginx/        # Reverse proxy config
├── scripts/
│   └── bootstrap.sh  # Local dev environment setup
└── .github/
    └── copilot-instructions.md
```

## Next steps

1. Epic 12 — Usage history and stock lifecycle
2. Epic 13 — Imports, labels, and operational polish

See [`BACKLOG.md`](BACKLOG.md) for the full phased plan and [`docs/ROADMAP.md`](docs/ROADMAP.md) for the phased roadmap.
