# MakerVault

MakerVault is a self-hosted inventory and knowledge system for electronics, IoT, workshop parts, tools, and technical reference material. It helps you track what you own, where it is stored, what it can do, which projects it has been used in, and what you could build with it. The system preserves important technical reference material locally and supports pluggable AI providers rather than hard-coding any single AI vendor.

> **Status:** Early-stage scaffold. Application services are containerised placeholders. No business logic has been implemented yet.

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

> **Note:** Application images are currently placeholders. The web and API services will return placeholder output until `apps/` are implemented. PostgreSQL and the document volume are active and persistent.

To stop: `docker compose -f infra/docker/docker-compose.yml down` or `make down`.

---



## Architecture

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python), containerised |
| Frontend | React + Vite + TypeScript, containerised |
| Database | PostgreSQL 16 (Docker, persistent volume) |
| Document store | Local filesystem volume (`/data/makervault/documents`) |
| Background jobs | Worker process (Python), containerised |
| AI abstraction | Pluggable provider layer |
| Reverse proxy | Nginx (Docker) |
| Deployment | Docker Compose on Ubuntu |

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for details.

## Repository structure

```
MakerVault/
├── README.md
├── AGENTS.md
├── Makefile
├── .gitignore
├── .editorconfig
├── LICENSE
├── apps/
│   ├── api/          # FastAPI backend
│   ├── web/          # React + Vite frontend
│   └── worker/       # Background job worker
├── docs/
│   ├── PRODUCT_VISION.md
│   ├── TECHNICAL_SPEC.md
│   ├── DATA_MODEL.md
│   ├── ARCHITECTURE.md
│   ├── ROADMAP.md
│   ├── API_SPEC.md
│   ├── UX_NOTES.md
│   └── DECISIONS.md
├── infra/
│   ├── docker/       # Docker Compose and service configs
│   └── nginx/        # Reverse proxy config
├── scripts/
│   └── bootstrap.sh  # Local dev environment setup
└── .github/
    └── copilot-instructions.md
```

## Next steps

1. Review and agree on the data model in [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md)
2. Review architectural decisions in [`docs/DECISIONS.md`](docs/DECISIONS.md)
3. Implement the FastAPI project in `apps/api/` and add its `Dockerfile`
4. Implement the React + Vite project in `apps/web/` and add its `Dockerfile`
5. Write the Nginx config in `infra/nginx/` to proxy `/api` → api and `/` → web
6. Create initial database migrations
7. Implement Phase 1 as described in [`docs/ROADMAP.md`](docs/ROADMAP.md)

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the full phased plan.
