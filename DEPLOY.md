# Deploy — Production

Architecture: **Frontend → Cloudflare Workers** (Next.js via OpenNext) · **Backend → Render** (FastAPI in Docker).

The backend can't run on Workers (yfinance / SQLAlchemy / APScheduler / SQLite need a real Python host), so it lives on Render and the Cloudflare frontend calls it directly over HTTPS (CORS is already configured).

```
Browser ──► Cloudflare Workers (frontend) ──► Render (FastAPI backend) ──► yfinance / FRED / Anthropic
```

Deploy the **backend first** — you need its URL to configure the frontend.

---

## 0. Prerequisites
- Code pushed to a GitHub repo.
- Accounts: [Render](https://render.com) (free) and [Cloudflare](https://dash.cloudflare.com) (free).
- `ANTHROPIC_API_KEY` (required). Optional: `FRED_API_KEY`, `NEWS_API_KEY`, Telegram tokens.

---

## 1. Backend → Render

Blueprint file: [`render.yaml`](./render.yaml) (already in the repo).

1. Render Dashboard → **New → Blueprint** → select your GitHub repo → Render reads `render.yaml`.
2. When prompted, fill the secret env vars (marked `sync:false`):
   - `ANTHROPIC_API_KEY` = `sk-ant-...`
   - `FRONTEND_URL` = leave blank for now (set it in step 3 after you know the Workers URL) — CORS also allows `*.workers.dev` via regex, so it works either way.
   - `FRED_API_KEY` = optional (enables the Economic page)
3. **Create** → wait for the build. Health check: `GET /health`.
4. Copy the service URL, e.g. `https://agent-invest-backend.onrender.com`. Verify:
   ```
   https://agent-invest-backend.onrender.com/health   → {"status":"healthy"}
   ```

> **Free plan notes:** the service sleeps after ~15 min idle (first request then takes ~50s to wake). The SQLite DB is **ephemeral** — it resets on each redeploy. For persistent history, add a Render Disk (paid) or switch `DATABASE_URL` to a Render Postgres instance.

Alternative host (same Dockerfile): **Railway** — New Project → Deploy from repo → set root to `backend/` → add the same env vars.

---

## 2. Frontend → Cloudflare Workers (OpenNext)

Already configured: [`frontend/wrangler.jsonc`](./frontend/wrangler.jsonc), [`frontend/open-next.config.ts`](./frontend/open-next.config.ts), and the `cf:deploy` script.

From the `frontend/` folder:

1. Point the frontend at your backend. Copy the template and edit the URL:
   ```powershell
   Copy-Item .env.production.example .env.production
   # edit .env.production:  NEXT_PUBLIC_API_URL=https://agent-invest-backend.onrender.com
   ```
   (`NEXT_PUBLIC_*` is baked in at build time, so it must be set before deploying.)

2. Log in to Cloudflare (opens a browser — run it yourself in the terminal):
   ```
   npx wrangler login
   ```

3. Build + deploy:
   ```
   npm run cf:deploy
   ```
   Wrangler prints the live URL, e.g. `https://agent-invest-frontend.<your-subdomain>.workers.dev`.

---

## 3. Lock CORS to your frontend (recommended)
Back in Render → the backend service → **Environment**, set:
```
FRONTEND_URL = https://agent-invest-frontend.<your-subdomain>.workers.dev
```
Save (the service redeploys). The API now explicitly allows your frontend origin (the `*.workers.dev` regex remains as a fallback for preview builds — remove `CORS_ALLOW_ORIGIN_REGEX` if you want to allow only this one origin).

---

## 4. Verify
Open the Workers URL and check:
- **ปฏิทินเหตุการณ์** (`/calendar`) — shows earnings/dividend events (proves frontend→backend works).
- **ระบบเรียนรู้** (`/insights`) — loads learning stats.
- **ตัวเลขเศรษฐกิจ** (`/economic`) — populated only if `FRED_API_KEY` is set; otherwise shows the setup notice.

If pages load but data is empty / CORS errors appear in the browser console, re-check `NEXT_PUBLIC_API_URL` (frontend) and `FRONTEND_URL` (backend).

---

## Redeploy later
- **Backend:** push to GitHub → Render auto-deploys (`autoDeploy: true`).
- **Frontend:** `npm run cf:deploy` again from `frontend/`.

## Custom domain (optional)
- Frontend: Cloudflare dashboard → Workers & Pages → your worker → **Custom Domains**.
- Then update the backend `FRONTEND_URL` to the custom domain.
