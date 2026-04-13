# apps/web

> **Status:** Placeholder. No implementation yet.

This directory will contain the MakerVault React + Vite frontend.

## Intended stack

- TypeScript
- React 18+
- Vite
- TanStack Query (for API data fetching)
- CSS framework: TBD (Tailwind CSS or similar)

## Planned structure (to be created)

```
apps/web/
├── src/
│   ├── main.tsx         # App entry point
│   ├── App.tsx
│   ├── components/      # Shared UI components
│   ├── pages/           # Route-level page components
│   ├── api/             # API client and query hooks
│   └── types/           # TypeScript types (generated from API or manual)
├── public/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
└── Dockerfile
```

## Getting started

See `scripts/bootstrap.sh` for environment setup.
