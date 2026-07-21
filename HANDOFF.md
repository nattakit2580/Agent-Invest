# Agent Invest - Project Handoff

Last updated: 2026-07-21 (Asia/Bangkok)

## Current assessment

The repository is ready for another developer or agent to clone, set up, test,
and continue as a self-hosted/single-tenant application after the changes in
this working tree are committed and pushed. It is not yet ready to operate as
an untrusted multi-user public SaaS; see Remaining decisions and risks.

At the time of this handoff:

- Git remote: `https://github.com/nattakit2580/Agent-Invest.git`
- Branch: `main`
- Baseline commit before this readiness pass: `0e48f01`
- Repository visibility is now public. During the 2026-07-21 audit, public
  `main` advanced from `0e48f01` to `962a0ee`; the local dirty working tree is
  still based on `0e48f01` and must integrate that remote commit before push.
- The readiness changes are local and are not yet committed, pushed, or
  redeployed. Always confirm with `git status` and the remote before relying on
  this point-in-time statement.

## Work completed in the readiness pass

### Onboarding and collaboration

- Expanded `README.md` with supported versions, one-click/manual/Docker setup,
  validation commands, security notes, collaboration guidance, and limitations.
- Reworked `setup.ps1` and `start.ps1` to use an isolated Python environment and
  exact frontend dependencies.
- Added `run.bat` for one-click Windows setup/start, including paths containing
  spaces or non-ASCII characters.
- Added `make_local_env.py` to create a local SQLite configuration without
  overwriting an existing `backend/.env`.
- Added `CONTRIBUTING.md`, `SECURITY.md`, this handoff, and `AGENTS.md`.
- Added `QUICKSTART_TH.md` for users who have never used Git and
  `docs/GITHUB_SHARING_TH.md` for repository visibility, collaborator,
  licensing, clean-clone, and release preparation.
- Made the beginner path prominent in README: download ZIP, extract outside
  OneDrive, and double-click `run.bat`. Git is optional for this path.

### Automated quality checks

- Added `.github/workflows/ci.yml` for Python security/syntax/smoke checks and
  frontend security/build checks on pushes and pull requests.
- Added `.github/dependabot.yml` for weekly pip, npm, and GitHub Actions updates.
- Added five offline smoke tests in `backend/tests/test_smoke.py` covering:
  health/root responses, empty-database reads, admin fail-closed behavior,
  Telegram webhook fail-closed behavior, and restrictive CORS defaults.

### Dependency and application security

- Upgraded vulnerable backend packages and pinned FastAPI/Starlette, requests,
  python-dotenv, aiohttp, and python-multipart to audited versions.
- Upgraded the frontend to Next.js `15.5.20` and OpenNext Cloudflare `1.20.1`.
- Pinned/overrode PostCSS `8.5.15` to remove the nested vulnerable version.
- Added `npm run audit:prod`.
- Removed broad default production CORS regexes; exact origins are preferred.
- Corrected admin documentation: there is no default admin password.
- Kept admin and Telegram-sensitive endpoints fail-closed when secrets are not
  configured.

### Containers and deployment configuration

- Added backend/frontend `.dockerignore` files to exclude secrets, dependency
  directories, caches, tests, databases, and build output from image contexts.
- Changed both Dockerfiles to use exact lockfiles where applicable and run as
  non-root users.
- Added missing Compose variables for admin, CORS, and internal backend routing.
- Standardized the documented/configured default OpenRouter model to the free
  `meta-llama/llama-3.3-70b-instruct:free` route.
- Documented that production should be protected by trusted identity/access
  controls before exposure to untrusted users.

### Cleanup performed

- Removed local `.env` files, the local SQLite runtime database, Python virtual
  environment, frontend build output, logs, reports, tunnel files/binary,
  TypeScript cache, and almost all `node_modules` content (roughly 1 GB total).
- The removed SQLite database contained no users or predictions. It contained
  14 cached calendar events and one monitor report. This cache is regenerable;
  it is not recoverable from Git.
- OneDrive still holds empty 0-byte placeholder directories for some ignored
  paths and an inaccessible zero-content `node_modules` reparse-point chain.
  They are local-only, ignored by Git, and do not affect a clean clone. Do not
  attempt risky OneDrive metadata resets just to remove them.

## Verification evidence

Passed in a fresh Python virtual environment:

- Dependency installation from `backend/requirements.txt`.
- `pip check`: no broken requirements.
- `pip-audit -r backend/requirements.txt`: no known vulnerabilities.
- Python compile check.
- Five backend smoke tests.

Passed from a clean copy of frontend source outside OneDrive:

- `npm ci` (505 packages from the committed lockfile).
- `npm run audit:prod`: 0 vulnerabilities.
- `npm run build` with Next.js 15.5.20: all 16 routes built successfully.

Also passed:

- `setup.ps1` and `start.ps1` PowerShell syntax checks.
- `run.bat` nested-quote command check for paths with spaces/non-ASCII text.
- `git diff --check`.
- Credential-pattern scan across tracked and new non-ignored files.
- An initial local Git history scan across 90 locally reachable commits found no
  high-confidence API token/private-key patterns and no non-placeholder
  assignments for sensitive environment variables.
- Gitleaks v8.30.1 (official release archive with verified SHA-256) scanned all
  88 commits reachable from a fresh clone of every public remote branch. Four
  findings were manually classified as false positives: three matched prose
  about JSON keys/enums and one matched the word `curl`.
- No sensitive filenames such as real `.env` files, keys, databases, logs, or
  reports were ever tracked in the public history.
- Public Git metadata does expose two Gmail commit-author addresses. One commit
  message also contains one production Telegram chat/channel identifier (shown
  in positive and negative form), and one Claude session URL is repeated across
  21 commit messages. These are not authentication secrets and no bot/API token
  was found, but they are public operational/personal metadata.
- GitHub Secret Scanning was disabled when queried after the repository became
  public; enable it in repository security settings for continuous monitoring.
- Detailed methods, redacted findings, limitations, and re-audit rules are in
  `docs/PUBLIC_SECURITY_AUDIT.md`.
- Live pre-change Render frontend and backend health endpoints returned HTTP 200.

Not run:

- `docker compose config` and image builds, because Docker CLI was unavailable
  on the audit machine.
- GitHub Actions itself, because the workflow has not been pushed yet.

## Remaining decisions and risks

1. Choose and add a `LICENSE`. Until then, external reuse rights are unclear.
   MIT is a common choice for broad reuse, but the owner must decide.
2. Decide whether to accept the exposed commit metadata described above or
   perform a coordinated history rewrite before wider distribution. A rewrite
   is disruptive, changes commit SHAs, and cannot erase clones already made.
3. Enable GitHub Secret Scanning and push protection.
4. Integrate remote commit `962a0ee` without losing the dirty readiness work,
   review the resulting diff, then commit/push and confirm CI passes.
5. Redeploy Render/Cloudflare and verify the deployed revision. The current live
   services still represent the older remote commit until that happens.
6. For a public multi-user service, add authentication, authorization, tenant
   isolation, per-user data boundaries, rate limits/abuse controls, and an
   operational privacy/data-retention policy.
7. Recharts 2.x is functional but no longer actively maintained. Its v3 upgrade
   has migration cost and should be handled as a separate tested change.
8. Run full Docker validation on a machine with Docker before claiming the
   container path is release-certified.

## Recommended next-agent sequence

1. Read `AGENTS.md` and `README.md`.
2. Run `git status --short`, inspect the full diff, and preserve existing work.
3. Confirm that public visibility is intentional, choose a license, and decide
   whether the exposed non-secret Git metadata warrants a history rewrite.
4. Use `docs/GITHUB_SHARING_TH.md` as the owner publishing checklist.
5. Run the required validation in `AGENTS.md` (prefer a folder outside OneDrive).
6. Commit/push only after explicit authorization, then observe CI.
7. Deploy only after explicit authorization and verify `/health`, the dashboard,
   CORS from the real frontend origin, and one representative API workflow.
8. Update this file with the commit, CI result, deployment revision, and any new
   residual risk.
