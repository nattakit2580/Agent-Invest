# Agent Invest - Agent Instructions

These instructions apply to the whole repository. Read this file, `README.md`,
and `HANDOFF.md` before changing code. Run `git status --short` first: the
working tree may contain intentional handoff work that has not been published.
Never discard or rewrite unrelated user changes.

Before changing visibility, rewriting Git history, rotating credentials, or
making a security claim, also read `docs/PUBLIC_SECURITY_AUDIT.md`.

## Project goal and scope

Agent Invest is a single-tenant investment-monitoring application. It combines
a FastAPI backend, a Next.js dashboard, scheduled data collection, OpenRouter
analysis, report exports, and Telegram delivery/community features.

It is suitable for self-hosting and trusted-team use. It is not currently a
multi-tenant public SaaS: there are no end-user accounts, tenant isolation, or
public-facing rate limits. Do not describe it as public-SaaS ready without
implementing and testing those controls.

## Repository map

- `backend/main.py`: FastAPI app, middleware, routers, and lifecycle.
- `backend/config.py`: environment-backed settings and safe defaults.
- `backend/api/`: HTTP route modules.
- `backend/agents/`: AI analysis agents.
- `backend/fetchers/`: external market/news/economic data fetchers.
- `backend/models/`: SQLAlchemy models.
- `backend/services/`: shared application and integration services.
- `backend/tasks/`: scheduled/background work.
- `backend/tests/`: offline smoke tests.
- `frontend/app/`: Next.js App Router pages.
- `frontend/components/`: shared UI components.
- `frontend/lib/`: frontend API/types/helpers.
- `.github/workflows/ci.yml`: required backend/frontend validation.
- `docs/PUBLIC_SECURITY_AUDIT.md`: redacted public-history audit and follow-up.
- `render.yaml`, `docker-compose.yml`: deployment definitions.

## Supported development environment

- Python 3.11 or newer.
- Node.js 20 LTS and npm.
- Windows quick start: `run.bat`.
- Beginner Windows instructions (Thai): `QUICKSTART_TH.md`.
- Separate Windows setup/start: `./setup.ps1`, then `./start.ps1`.
- Cross-platform manual and Docker instructions: `README.md`.

Prefer a normal local folder on Windows instead of a OneDrive-synced folder.
OneDrive placeholder/reparse-point behavior can corrupt `node_modules` and
`.venv`. This repository may itself be inspected inside OneDrive, so ignored
empty placeholder directories are not evidence that source files are missing.

## Configuration and security rules

- Never commit `.env`, API keys, Telegram tokens, admin tokens, customer data,
  logs, local databases, virtual environments, or build output.
- Update the relevant `.env.example` whenever a setting is added or changed.
- Local setup uses SQLite and disables RAG. RAG requires PostgreSQL/pgvector.
- Keep `CORS_ALLOW_ORIGIN_REGEX` blank by default. Prefer exact production
  origins in `CORS_ALLOW_ORIGINS`.
- Admin APIs must fail closed when `ADMIN_PASSWORD` is blank.
- Telegram webhook/admin endpoints must fail closed when their secrets are
  blank. Do not weaken these behaviors to simplify local development.
- Do not add real credentials to tests, fixtures, screenshots, or documentation.
- Preserve the non-root Docker runtime users and `.dockerignore` coverage.

## Dependency rules

- Python runtime dependencies are pinned in `backend/requirements.txt`.
- Frontend installs must use `npm ci` and the committed lockfile.
- Avoid dependency churn unrelated to the task.
- When updating dependencies, run both vulnerability audits and the relevant
  build/tests. Keep the production audit at zero high/critical findings.

## Required validation

Backend:

```powershell
cd backend
python -m compileall -q .
python -m unittest discover -s tests -v
pip-audit -r requirements.txt
```

Frontend:

```powershell
cd frontend
npm ci
npm run audit:prod
npm run build
```

Repository checks:

```powershell
git diff --check
git status --short
```

Use the narrowest relevant test while iterating, then run the broader checks
above before handoff. If Docker files change, also run `docker compose config`
and a container build when Docker is available. Record any skipped check and
the reason in `HANDOFF.md`.

## Change and handoff discipline

- Keep edits scoped and follow nearby patterns.
- Add or update tests for shared backend behavior and security defaults.
- Update README/setup/deployment docs when commands or environment variables
  change.
- Treat generated files as disposable; do not commit ignored artifacts.
- Before publishing, review the entire diff, scan for secrets, and verify the
  Git remote/branch.
- Update `HANDOFF.md` after material changes: summarize behavior, files,
  validation, deployment status, data impact, and remaining risks.
- Do not mark a change deployed merely because it builds locally. Confirm the
  remote commit and live revision separately.
