# infra/nginx

> **Status:** Placeholder. No Nginx configuration has been written yet.

This directory will contain the Nginx reverse proxy configuration for production deployment.

## Planned contents

```
infra/nginx/
├── nginx.conf           # Main Nginx config
├── default.conf         # Site config: proxy to API and serve frontend
└── README.md            # This file
```

## Intended behaviour

- Serve the React frontend static files from `/`
- Proxy `/api/` requests to the FastAPI backend
- Handle HTTPS termination (certificate management TBD — Let's Encrypt or self-signed for local use)
- Set appropriate cache headers for static assets
- Do not expose the database, worker, or Redis directly

## Notes

- For local development, Nginx is optional; Vite's dev server and `uvicorn` can be used directly
- In production Docker Compose, Nginx is the only service with a host-exposed port
