# Agent Invest - Project Handoff

Last updated: 2026-07-27 (Asia/Bangkok)

## 2026-07-27 update: daily Telegram monitor was silently failing since ~2026-07-25

**Symptom:** the owner noticed the daily monitor report (scheduled 08:30
Asia/Bangkok, sent to the Telegram channel) had not arrived on 2026-07-27
(the calendar-events alert still arrived, which is why it wasn't obvious the
whole pipeline was down). Last successful send before that was 2026-07-25.

**Root cause:** `POST /telegram/monitor/run` (the endpoint the external Render
Cron Job `agent-invest-daily-trigger` hits every 5 min, 08:25-08:55
Asia/Bangkok, to work around the backend's free-tier sleep) used to run
`send_daily_telegram_monitor()` synchronously and only return once it
finished. `build_daily_monitor_report()` does ~20 sequential per-symbol
`yfinance` fetches plus news/FRED/LLM calls, which can take well over a
minute — long enough to blow past the cron's `--max-time 60` on a cold
Render free-tier instance. Confirmed live in the Render dashboard: the cron
job's run history showed every invocation on 2026-07-27 failing with
`curl: (28) Operation timed out after 60002 milliseconds with 0 bytes
received` (exit status 28), i.e. the backend never got a chance to respond
in time, not an auth/config problem. `GET /telegram/status` on the live
backend confirmed config was correct throughout (`admin_token_configured`,
`daily_report_enabled`, `daily_report_time: 08:30` all true/correct), which
ruled out the `TELEGRAM_ADMIN_TOKEN` mismatch that an earlier pass's
comments had flagged as the previously-seen failure mode.

**Fix (uncommitted-file names below are now committed):**
- `backend/api/telegram.py` — `run_daily_monitor` (`/telegram/monitor/run`)
  now returns immediately (`{"ok": true, "queued": true, ...}`) and runs
  `send_daily_telegram_monitor` via FastAPI `BackgroundTasks` instead of
  blocking the HTTP response on the full report build. The external cron's
  60s timeout can no longer be hit regardless of how long report generation
  takes.
- `backend/tasks/scheduler.py` — added a non-blocking `threading.Lock`
  (`_monitor_send_lock`) around the actual send so overlapping triggers
  (in-process 08:30 cron, 90s-after-boot catch-up, and the external cron's
  repeated 5-min pings during its 30-min window) can't run
  `build_daily_monitor_report()` concurrently and send duplicate reports if
  one run is still in flight when the next trigger fires. Split the old
  single function into a thin `send_daily_telegram_monitor` (lock guard) and
  `_send_daily_telegram_monitor_locked` (the original body, unchanged).

**Verification (this pass):** OneDrive-synced folders can corrupt a fresh
`.venv` (per `AGENTS.md`), so verified in a clean copy at a plain local path
instead of in place:
- `python -m unittest discover -s tests -v`: 5/5 smoke tests still pass
  unmodified.
- Manual check with `fastapi.testclient.TestClient` (real `main.py` app,
  SQLite, lifespan startup so `init_db()` runs): `POST /telegram/monitor/run`
  with a valid `X-Admin-Token` returned HTTP 200 with `{"queued": true}` in
  **0.047s**, and the background task was observed still running afterward
  (real `yfinance` HTTP calls for the default watchlist symbols logged to
  stdout after the response had already been returned) — direct evidence the
  fix decouples the HTTP response from the report-build duration.
- Did **not** verify the live Render cron job's next scheduled run in this
  pass (would require waiting for/observing 08:25-08:55 Asia/Bangkok the
  next day, or the owner manually triggering the cron job's "Run now" in the
  Render dashboard after this deploy goes live) — next agent/owner should
  confirm the next 08:xx run shows green in the Render cron job's run
  history, and that the Telegram channel actually received that day's
  report.

**Not changed / still true:** the underlying reason `build_daily_monitor_report()`
takes so long (sequential per-symbol fetches, sequential LLM calls) was not
addressed — the fix only makes the timeout un-hittable, it doesn't make
report generation faster. If the watchlist grows much further or `yfinance`/
OpenRouter latency increases, generation time could grow further; this is
fine as long as nothing external still assumes a synchronous, bounded-time
response from `/telegram/monitor/run` (nothing currently does — grepped
`frontend/` and `docs/` for callers, found none besides the Render cron).
Parallelizing the per-symbol fetches in `build_watchlist_summary()` would
reduce report-build latency directly if that's ever wanted, but was
out of scope for this pass (pure timeout/robustness fix only).

## Current assessment

The readiness pass is committed, pushed, and live. CI is green, Render has
redeployed both services, and the site is reachable and healthy. The
repository is ready for another developer or agent to clone, set up, test,
and continue as a self-hosted/single-tenant application. It is not yet ready
to operate as an untrusted multi-user public SaaS; see Remaining decisions
and risks.

- Git remote: `https://github.com/nattakit2580/Agent-Invest.git`
- Branch: `main`
- Published commit: `e38c6e0`
- Repository visibility: public.
- CI (`.github/workflows/ci.yml`) is registered and green on `main`:
  https://github.com/nattakit2580/Agent-Invest/actions/runs/29876940421
- Render frontend and backend both returned HTTP 200 / `{"status":"healthy"}`
  after the deploy, and the new `/users` admin page and `/telegram/users` API
  route (added by `d264ea7`) are live in production.

## What shipped in this pass

Commits landed on `main`, in order:

1. `418744a` - readiness pass: onboarding docs, MIT `LICENSE`, GitHub Actions
   CI + Dependabot config, five backend smoke tests, Docker hardening
   (`.dockerignore`, non-root users, exact lockfiles), dependency security
   upgrades (FastAPI, aiohttp, Next.js 15.5.20, python-dotenv,
   python-multipart), and a fix to the `OPENROUTER_MODEL` **code-level
   default** in `backend/config.py` + both `.env.example` files (still
   pointed at the retired `meta-llama/llama-3.3-70b-instruct:free`).
2. `66b1ae1` - merged two commits that landed on `origin/main` from a
   concurrent session while this pass was in progress:
   - `962a0ee` fix: `OPENROUTER_MODEL` in `render.yaml` (same retired-model
     404 bug, the deployed-environment side of it).
   - `d264ea7` feat: web admin user management (`GET/POST
     /telegram/users*`, `frontend/app/users/page.tsx`) - set tier, grant/
     reset quota per Telegram user from `/admin`.
   No merge conflicts; the two sides touched different lines of `render.yaml`.
3. `5fcac9a` - merged `origin/feat/telegram-ai-chat-feedback` (`91b9480`):
   `/analyze` now sends an immediate "processing" message and a 10s
   heartbeat with elapsed time/stage in Telegram instead of going silent for
   ~45s, then edits the same message into the final result. Chosen after
   surveying all 17 remote/local branches - this was the only one with
   genuinely unmerged work; the rest (including the 3 `integrate/*`
   branches) were already ancestors of `main` or superseded.
4. `e38c6e0` - CI caught a **freshly published** high-severity advisory
   (GHSA-f88m-g3jw-g9cj, CVE-2026-33327/33328/35590/35591 in libvips) for
   `sharp <0.35.0`, pulled in transitively by Next.js's image optimizer and
   by `wrangler`/`miniflare`. Fixed via an `npm overrides` pin to
   `sharp@0.35.3` (same pattern as the existing `postcss` pin) instead of
   the breaking Next.js downgrade `npm audit fix --force` would have done.

### GitHub repository settings changed

- Added `LICENSE` (MIT, user's explicit choice among MIT/Apache-2.0/
  proprietary/undecided).
- Enabled via API: Secret Scanning, Secret Scanning Push Protection,
  Dependabot Security Updates. (`secret_scanning_validity_checks` and
  `secret_scanning_non_provider_patterns` did not toggle on via the API in
  this pass - re-check/enable manually in repo Settings -> Security if
  desired.)
- Enabling Dependabot triggered an immediate dependency-graph scan and a
  batch of Dependabot version-bump PRs (autoprefixer, @types/node, uvicorn,
  numpy, recharts, aiohttp, sharp, etc.) plus 82 alerts against the
  pre-readiness-pass dependency state; these were expected to (and did,
  where checked) auto-resolve as `main` advanced past them. Review/triage
  the open Dependabot PRs separately - they were not merged in this pass.

## Verification evidence

Passed in this session, in a clean environment (fresh venv / clean copy
outside OneDrive, per `AGENTS.md`):

- `python -m compileall -q .`
- `python -m unittest discover -s tests -v`: 5/5 smoke tests pass.
- `pip-audit -r backend/requirements.txt` (isolated venv): no known
  vulnerabilities.
- `npm ci` (505 packages from the committed lockfile).
- `npm run audit:prod`: 0 vulnerabilities (after the `sharp` pin).
- `npm run build` with Next.js 15.5.20: all 17 routes built successfully
  (16 + the new `/users` page).
- `git diff --check`, `git status --short`, and a secret-pattern grep over
  the full pushed diff: clean.
- GitHub Actions CI on `main` (`e38c6e0`): both `frontend` and `backend`
  jobs green.
- Live: `GET /health` -> `{"status":"healthy"}`; frontend root -> 200;
  `/telegram/users` -> 401 (endpoint exists, requires admin password);
  `/users` -> 200.

Not run in this session (still valid from the prior audit unless noted
otherwise above):

- Full live `/analyze` round-trip against OpenRouter (would consume a real
  API call/quota) - not re-run here. The prior session already verified a
  live `POST /analyze` returned a real 4-agent result after applying the
  same model fix via the admin API.
- `docker compose config` / container build - Docker CLI unavailable.
- `secret_scanning_validity_checks` / `secret_scanning_non_provider_patterns`
  - did not enable via API; needs manual toggle if wanted.

## Remaining decisions and risks

1. **Dependabot PRs are open, unreviewed.** Several version-bump PRs landed
   automatically the moment Dependabot was enabled (e.g. recharts 2->3,
   numpy 1.26->2.5, uvicorn 0.30->0.51, @types/node 20->26). Triage these
   individually - several are major-version bumps with real breaking-change
   risk (recharts v3 migration is already flagged as separate work below).
2. Decide whether to accept the exposed commit metadata (two Gmail author
   addresses, one Telegram chat/channel identifier, one repeated Claude
   session URL across ~21+ commit messages - see
   `docs/PUBLIC_SECURITY_AUDIT.md`) or perform a coordinated history
   rewrite. A rewrite is disruptive, changes commit SHAs, and cannot erase
   clones already made. Not done in this pass.
3. `secret_scanning_validity_checks` and
   `secret_scanning_non_provider_patterns` are still disabled - enable
   manually in GitHub repo Settings -> Security if wanted.
4. For a public multi-user service, still need authentication, authorization,
   tenant isolation, per-user data boundaries, rate limits/abuse controls,
   and an operational privacy/data-retention policy.
5. Recharts 2.x is functional but no longer actively maintained; a v3
   upgrade has migration cost and should be a separate tested change (a
   Dependabot PR proposing this already exists - see #1).
6. Run full Docker validation (`docker compose config` + image build) on a
   machine with Docker before claiming the container path is
   release-certified.
7. 14 now-superseded remote branches and several local `integrate/*`
   branches are confirmed ancestors of `main` (see branch survey below) -
   safe to delete if the owner wants a cleaner branch list, but left
   untouched in this pass since deletion wasn't explicitly requested.

## Branch survey (this session)

Surveyed all 14 remote feature/phase branches plus the local `integrate/*`
branches to check for unmerged work. Result: 16 of 17 originally-listed
branches were already ancestors of `main` or fully superseded by later
commits on `main` (verified with `git merge-base --is-ancestor` plus
spot-checks of representative file content). Only
`feat/telegram-ai-chat-feedback` (`91b9480`) had genuinely unmerged work; it
was reviewed and merged as `5fcac9a` above. No further branch merges are
recommended from this survey; a later `git fetch` may surface new branches
from the same concurrently-active session (see below).

## Concurrent-session note

During this pass, another agent/session (author `Anopprut
<r.nopprut@gmail.com>`, commit trailers show `Co-Authored-By: Claude Fable 5`)
was actively pushing directly to `origin/main` and editing files in this
same local working tree at the same time (e.g. `962a0ee`, `d264ea7`, and
`docs/PUBLIC_SECURITY_AUDIT.md` appeared mid-session, unprompted by this
agent). Remote state was re-fetched before each merge/push in this pass and
no work was discarded, but the next agent should also re-check
`git fetch origin main` and `git status` immediately before acting, since
`main` may have moved again since this document was written.

## Recommended next-agent sequence

1. Read `AGENTS.md`, `README.md`, and this file.
2. Run `git fetch origin main && git status --short` - main may have moved
   further; another session may still be active concurrently.
3. Triage the open Dependabot PRs (see Remaining decisions #1).
4. Decide on the commit-metadata question (see Remaining decisions #2) and
   on deleting the 16 confirmed-superseded branches.
5. Run Docker validation if Docker is available.
6. Update this file with any new commit, CI result, deployment revision, or
   residual risk.
