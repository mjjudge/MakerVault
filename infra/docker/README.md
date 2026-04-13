# infra/docker

> **Status:** Placeholder. No Docker configuration has been written yet.

This directory will contain the Docker Compose configuration and any service-specific Docker configuration files.

## Planned contents

```
infra/docker/
├── docker-compose.yml        # Primary Compose file for production-like local deployment
├── docker-compose.dev.yml    # Dev overrides (e.g. volume mounts for hot reload)
├── .env.example              # Example environment variable file
└── README.md                 # This file
```

## Planned services

| Service | Image | Notes |
|---|---|---|
| `db` | `postgres:16` | Primary database |
| `api` | `./apps/api` | FastAPI backend |
| `web` | `./apps/web` | React frontend (served via Nginx in prod) |
| `worker` | `./apps/worker` | Background worker |
| `nginx` | `nginx:alpine` | Reverse proxy (production) |
| `redis` | `redis:alpine` | Optional; only if Celery is chosen for the worker |

## Notes

- All services communicate over a private Docker network (`makervault_net`)
- Only `nginx` is exposed to the host network (ports 80 and 443)
- The document store is a named Docker volume (`makervault_documents`) mounted into `api` and `worker`
- Environment variables for secrets (AI API keys, DB password) should be provided via a `.env` file — **never committed to the repository**
