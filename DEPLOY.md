# Deploy MVP On Render

This repo is now prepared for a simple Render MVP deployment:

```text
Browser -> Render frontend (Next.js) -> /api rewrite -> Render backend (FastAPI) -> Render PostgreSQL
```

The blueprint file is `render.yaml`. It creates:

- `agent-invest-db` - PostgreSQL database
- `agent-invest-backend` - FastAPI backend from `backend/Dockerfile`
- `agent-invest-frontend` - Next.js frontend from `frontend/`

## 1. Required Secret

Create an OpenRouter key and add it to the backend service when Render asks for secret env vars:

```text
OPENROUTER_API_KEY=sk-or-...
```

The default model is already set to:

```text
meta-llama/llama-3.3-70b-instruct:free
```

Optional secrets:

```text
NEWS_API_KEY=
FRED_API_KEY=
EMBEDDING_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHANNEL_ID=
TELEGRAM_ADMIN_TOKEN=
```

For the MVP website, only `OPENROUTER_API_KEY` is required for `/analyze`.

This dashboard is single-tenant. Before exposing it to untrusted users, add an
identity-aware access layer and rate limits; repository privacy does not protect
a public deployment URL.

## 2. Deploy From Blueprint

1. Push this repo to GitHub.
2. In Render: New -> Blueprint.
3. Select this repo.
4. Confirm the services from `render.yaml`.
5. Fill `OPENROUTER_API_KEY` for `agent-invest-backend`.
6. Create the blueprint and wait for both services to deploy.

Expected URLs:

```text
Backend:  https://agent-invest-backend.onrender.com
Frontend: https://agent-invest-frontend.onrender.com
```

Health check:

```text
https://agent-invest-backend.onrender.com/health
```

Expected response:

```json
{"status":"healthy"}
```

## 3. Verify MVP Pages

Open the frontend URL and verify:

- `/` dashboard loads
- `/analyze` can analyze a symbol such as `AAPL` or `NVDA`
- `/predictions` shows saved predictions after one analysis
- `/accuracy` loads without crashing
- `/economic` works when `FRED_API_KEY` is set, otherwise it should show empty/setup state
- `/calendar` loads upcoming events when market data is available

## 4. Notes

- The frontend uses `/api` and Next.js rewrites to `BACKEND_URL`, so customers only need the frontend URL.
- `RAG_ENABLED=false` in Render by default for MVP reliability. Enable it later after setting `EMBEDDING_API_KEY` and confirming the vector dimension.
- Free Render services may sleep after idle time, so the first request can be slow.
- Do not commit real API keys or Telegram tokens.
