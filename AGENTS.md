# AGENTS.md

Instructions for coding agents (Copilot, automated tools, and future AI-assisted contributors) working in this repository.

---

## General behaviour

- **Do not guess when requirements are unclear.** Stop and ask. Flag ambiguity in a comment or PR description rather than inventing a solution.
- **Prefer small, reviewable changes.** A focused PR that does one thing well is always preferred over a large sweeping change.
- **Keep implementation aligned to the documentation.** If the code diverges from `docs/`, update the docs. If the docs are wrong, fix the docs.
- **Update documentation when behaviour or architecture changes.** Do not leave docs describing something that no longer exists.

## Commits

- Use [Conventional Commits](https://www.conventionalcommits.org/) format: `type(scope): description`
- Common types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`
- Keep commit messages concise and descriptive
- Reference issue numbers where relevant

## Architecture

- Do not replace agreed architecture without writing it up in `docs/DECISIONS.md` first
- Do not add hidden dependencies or external services without documenting them
- Do not hard-code any AI provider; use the provider abstraction layer
- The database is the source of truth; AI is used for reasoning, enrichment, and suggestion only
- Favour maintainability and explicitness over cleverness

## Adding dependencies

- Record the reason for any new dependency in a PR description or relevant doc
- Do not introduce dependencies that phone home, collect telemetry, or require external accounts without explicit approval
- Check for existing utilities before adding a new library

## Testing

- Write tests for new behaviour; do not remove or disable existing tests
- Tests live alongside the code they cover (`apps/api/tests/`, `apps/web/src/__tests__/`, etc.)
- Prefer integration tests for API endpoints; unit tests for pure logic

## File layout

- Application code lives in `apps/`
- Infrastructure config lives in `infra/`
- Documentation lives in `docs/`
- Automation scripts live in `scripts/`
- Do not create files outside these boundaries without a documented reason

## What to do when unsure

1. Read the relevant doc in `docs/`
2. Check `docs/DECISIONS.md` for prior choices
3. Check open issues or PRs for context
4. If still unclear, stop and ask rather than proceed on an assumption
