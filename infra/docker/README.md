# infra/docker

Docker Compose configuration for MakerVault. This is the primary way to run the system locally and in self-hosted production.

## Contents

```
infra/docker/
├── docker-compose.yml   # Primary Compose file
├── .env.example         # Template for required environment variables
└── README.md            # This file
```

## Quick start

```sh
cp infra/docker/.env.example infra/docker/.env
# Edit infra/docker/.env — set POSTGRES_PASSWORD and SECRET_KEY at minimum
docker compose -f infra/docker/docker-compose.yml up
```

Or from the repository root using the Makefile:

```sh
cp infra/docker/.env.example infra/docker/.env
make up
```

## Services

| Service  | Image (scaffold)     | Role                              | Exposed port |
|----------|----------------------|-----------------------------------|--------------|
| `nginx`  | `nginx:alpine`       | Reverse proxy; entry point        | 80 (configurable) |
| `web`    | `nginx:alpine`\*     | React + Vite frontend             | internal     |
| `api`    | `python:3.12-slim`\* | FastAPI backend                   | internal     |
| `worker` | `python:3.12-slim`\* | Background job processor          | none         |
| `db`     | `postgres:16-alpine` | Primary PostgreSQL database       | internal     |

\* Placeholder image — will be replaced with application-specific `Dockerfile` builds once `apps/` are implemented.

## Volumes

| Volume      | Mount path (container)         | Purpose                            |
|-------------|--------------------------------|------------------------------------|
| `db_data`   | `/var/lib/postgresql/data`     | PostgreSQL data — persistent       |
| `documents` | `/data/makervault/documents`   | Local document store — **do not delete** |

Both volumes are named Docker volumes managed by Compose and persist across container restarts and re-creations.

## Networking

All services are on the private `makervault_net` bridge network. Only `nginx` is exposed to the host. The API and database are not directly reachable from outside the Docker network.

## Environment variables

Copy `.env.example` to `.env` and set values before first run. Required fields:

- `POSTGRES_PASSWORD` — database password
- `SECRET_KEY` — API signing key (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)

See `.env.example` for the full list including optional AI provider keys.

> **Never commit `.env` to version control.** It is excluded via `.gitignore`.
