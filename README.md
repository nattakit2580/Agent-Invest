# Agent Invest

Agent Invest is a private full-stack investment monitoring system. It includes a FastAPI backend, a Next.js dashboard, AI-assisted investment analysis, prediction tracking, report exports, and a Telegram bot for channels, private chats, and communities.

This README is intentionally ASCII-safe so it renders correctly in GitHub, Windows terminals, and editors that may not auto-detect UTF-8.

## What The System Does

- Analyze investment symbols with multiple AI agents.
- Store predictions and compare them with later market prices.
- Track prediction accuracy by timeframe and symbol.
- Fetch market data, news, economic agenda, and IPO agenda.
- Build daily monitor reports for Telegram.
- Send one-way updates to a Telegram channel.
- Reply to private Telegram bot chats by command or natural-language intent.
- Collect Telegram community analytics for topics, intents, keywords, and activity.
- Send limited previews to a free community and full reports to a paid target.

## Main Parts

### Backend

Backend source lives in `backend/`.

Stack:

- Python 3.11+
- FastAPI
- SQLAlchemy
- SQLite by default
- APScheduler
- yfinance
- feedparser
- OpenRouter integration with DeepSeek as the default model

Local API docs:

```text
http://localhost:8000/docs
```

### Frontend

Frontend source lives in `frontend/`.

Stack:

- Next.js 14
- React 18
- TypeScript
- Tailwind CSS
- Recharts
- lucide-react

Main pages:

- `/` - main dashboard
- `/analyze` - create a new analysis
- `/predictions` - prediction history
- `/accuracy` - accuracy dashboard
- `/export` - export tools
- `/telegram` - Telegram analytics dashboard

### Telegram Bot

The Telegram system supports 3 modes.

1. Channel broadcast
   - Sends one-way monitor updates to a Telegram channel.

2. Private bot chat
   - Users can ask the bot for specific information.
   - Supported commands include:

```text
/news
/watchlist
/ipo
/ipohk
/checkaddress <wallet>
/report
/help
```

Natural-language intent matching is also supported. Example meanings:

```text
Ask for Hong Kong IPO updates
Ask for today's watchlist
Ask to check a crypto wallet address
Ask for noteworthy market news
```

3. Free and paid community
   - Free community gets a limited public preview.
   - Paid target gets the full report.
   - Incoming private/group messages are stored for analytics.

Full Telegram setup details are in `docs/telegram-bot.md`.

## Project Structure

```text
.
|-- backend/
|   |-- agents/              # AI analysis agents
|   |-- api/                 # FastAPI routers
|   |-- fetchers/            # Market, news, and agenda fetchers
|   |-- models/              # SQLAlchemy and Pydantic models
|   |-- services/            # Telegram and monitor report services
|   |-- tasks/               # Scheduler jobs
|   |-- utils/
|   |-- main.py              # FastAPI entrypoint
|   `-- requirements.txt
|-- frontend/
|   |-- app/                 # Next.js app routes
|   |-- components/
|   |-- lib/
|   `-- package.json
|-- data/
|   |-- ipo_watchlist.json
|   `-- ipo_watchlist.example.json
|-- docs/
|   `-- telegram-bot.md
|-- docker-compose.yml
|-- setup.ps1
`-- start.ps1
```

## Local Setup

### Option A: PowerShell scripts

Install dependencies:

```powershell
.\setup.ps1
```

Start backend and frontend:

```powershell
.\start.ps1
```

Default URLs:

```text
Frontend: http://localhost:3000
Backend:  http://localhost:8000
API Docs: http://localhost:8000/docs
```

### Option B: Manual setup

Backend:

```powershell
cd backend
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

## Environment Variables

Edit this file after setup:

```text
backend/.env
```

Important values:

```env
OPENROUTER_API_KEY=
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DATABASE_URL=sqlite:///./agent_invest.db
NEWS_API_KEY=
FRONTEND_URL=http://localhost:3000

TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=
TELEGRAM_CHANNEL_ID=
TELEGRAM_COMMUNITY_CHAT_ID=
TELEGRAM_PAID_CHAT_ID=
TELEGRAM_WEBHOOK_SECRET_TOKEN=
TELEGRAM_ADMIN_TOKEN=

TELEGRAM_DAILY_REPORT_ENABLED=false
TELEGRAM_COMMUNITY_REPORT_ENABLED=false
TELEGRAM_PAID_REPORT_ENABLED=false
TELEGRAM_DAILY_REPORT_HOUR=8
TELEGRAM_DAILY_REPORT_MINUTE=30
TELEGRAM_TIMEZONE=Asia/Bangkok
```

Do not commit `backend/.env`. It is ignored by `.gitignore`.

## Telegram Setup Summary

1. Create a bot with `@BotFather`.
2. Copy the API token to `TELEGRAM_BOT_TOKEN`.
3. Set `TELEGRAM_BOT_USERNAME` to the bot username without `@`.
4. Add the bot as admin to the channel and group.
5. Disable bot privacy mode in BotFather if group analytics should collect normal group messages.
6. Find chat IDs with Telegram `getUpdates` or `backend/get_group_id.py`.
7. Register the webhook with a public HTTPS backend URL.

Register webhook example:

```bash
curl -X POST http://localhost:8000/telegram/webhook/register \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: <TELEGRAM_ADMIN_TOKEN>" \
  -d "{\"webhook_url\":\"https://your-public-domain.com/telegram/webhook\",\"drop_pending_updates\":true}"
```

Webhook URL must be public HTTPS. Cloudflare Tunnel can be used for local testing.

## Useful API Endpoints

Health:

```text
GET /health
```

Telegram:

```text
GET  /telegram/status
POST /telegram/reports/preview
POST /telegram/reports/send
POST /telegram/broadcast
POST /telegram/webhook
POST /telegram/webhook/register
GET  /telegram/webhook/info
GET  /telegram/analytics
GET  /telegram/reports
```

Predictions and accuracy:

```text
POST /analyze
GET  /predictions
GET  /predictions/{id}
POST /predictions/{id}/auto-compare
GET  /accuracy
```

## Docker Compose

Set values in a root `.env` file, then run:

```powershell
docker compose up --build
```

Services:

```text
Backend:  http://localhost:8000
Frontend: http://localhost:3000
```

## Validation Commands

Backend syntax check:

```powershell
python -m compileall backend
```

Frontend production build:

```powershell
cd frontend
npm run build
```

Git checks:

```powershell
git diff --check
git status -sb
```

## Security Notes

- This GitHub repository is private.
- `.env`, logs, local databases, `node_modules`, `.next`, and runtime tunnel files are ignored.
- Never commit real API keys, Telegram bot tokens, or admin tokens.
- Use `TELEGRAM_WEBHOOK_SECRET_TOKEN` to reject fake webhook requests.
- Use `TELEGRAM_ADMIN_TOKEN` for admin-only Telegram endpoints.

## Collaboration

To invite a friend to this private repository:

```text
GitHub repository -> Settings -> Collaborators -> Add people
```

Recommended permission for normal development is `Write`.

## Current Limitations

- Wallet checking currently identifies address type and returns explorer links. Balance and risk scoring need chain explorer API integration.
- Free vs paid content is split by sending different reports to different Telegram targets. It does not yet verify paid membership inside one shared group.
- News and IPO quality depends on configured RSS sources and manual `data/ipo_watchlist.json` entries.
