# Agent Invest

Agent Invest is a full-stack investment monitoring and AI analysis system. It combines a FastAPI backend, a Next.js dashboard, market/news fetchers, multi-agent analysis, prediction tracking, accuracy review, export tools, and a Telegram bot system for channels, private chats, and communities.

## What This Project Does

- Analyze investment symbols with multiple AI agents.
- Store predictions and compare them with later market prices.
- Track model accuracy by timeframe and symbol.
- Build market monitor reports from watchlists, RSS/news sources, IPO agenda, and optional AI summaries.
- Send Telegram updates to a one-way channel.
- Let users chat privately with the Telegram bot using commands or natural language.
- Collect Telegram community/private-chat analytics for upsell and product insight.
- Split free community updates and paid/subscriber updates.

## Main Features

### Web Dashboard

- Dashboard overview
- New symbol analysis
- Prediction history
- Prediction detail and auto-compare
- Accuracy dashboard
- Export page
- Telegram analytics dashboard

Frontend runs with Next.js in `frontend/`.

### Backend API

Backend runs with FastAPI in `backend/`.

Key API groups:

- `/analyze`
- `/predictions`
- `/accuracy`
- `/export`
- `/telegram`

Open local API docs at:

```text
http://localhost:8000/docs
```

### Telegram Bot Modes

1. **Channel broadcast**
   Sends one-way updates to a Telegram channel.

2. **Private chat bot**
   Users can chat with the bot using commands such as:

   ```text
   /news
   /watchlist
   /ipo
   /ipohk
   /checkaddress <wallet>
   /report
   /help
   ```

   Natural language intent matching is also supported, for example:

   ```text
   เธญเธขเธฒเธเธ”เธน IPO เธฎเนเธญเธเธเธ
   เธซเธธเนเธเธ—เธตเนเธเธงเธฃเธ•เธดเธ”เธ•เธฒเธกเธงเธฑเธเธเธตเน
   เธญเธขเธฒเธเธ•เธฃเธงเธเธเธฃเธฐเน€เธเนเธฒเธเธฃเธดเธเนเธ• 0x0000000000000000000000000000000000000000
   เธเธญเธเนเธฒเธงเธ—เธตเนเธเนเธฒเธเธฑเธเธ•เธฒ
   ```

3. **Community and paid content**
   - Free community receives limited public previews.
   - Paid/subscriber target receives full reports.
   - Group/private messages are stored for topic, intent, keyword, and activity analytics.

More details are in [docs/telegram-bot.md](docs/telegram-bot.md).

## Tech Stack

### Backend

- Python 3.11+
- FastAPI
- SQLAlchemy
- SQLite by default
- APScheduler
- yfinance
- feedparser
- Anthropic API integration

### Frontend

- Next.js 14
- React 18
- TypeScript
- Tailwind CSS
- Recharts
- lucide-react

## Project Structure

```text
.
โ”โ”€โ”€ backend/
โ”   โ”โ”€โ”€ agents/              # AI analysis agents
โ”   โ”โ”€โ”€ api/                 # FastAPI routers
โ”   โ”โ”€โ”€ fetchers/            # Market/news/agenda fetchers
โ”   โ”โ”€โ”€ models/              # SQLAlchemy and Pydantic models
โ”   โ”โ”€โ”€ services/            # Telegram and monitor report services
โ”   โ”โ”€โ”€ tasks/               # Scheduler jobs
โ”   โ”โ”€โ”€ utils/
โ”   โ”โ”€โ”€ main.py              # FastAPI entrypoint
โ”   โ””โ”€โ”€ requirements.txt
โ”โ”€โ”€ frontend/
โ”   โ”โ”€โ”€ app/                 # Next.js app routes
โ”   โ”โ”€โ”€ components/
โ”   โ”โ”€โ”€ lib/
โ”   โ””โ”€โ”€ package.json
โ”โ”€โ”€ data/
โ”   โ”โ”€โ”€ ipo_watchlist.json
โ”   โ””โ”€โ”€ ipo_watchlist.example.json
โ”โ”€โ”€ docs/
โ”   โ””โ”€โ”€ telegram-bot.md
โ”โ”€โ”€ docker-compose.yml
โ”โ”€โ”€ setup.ps1
โ””โ”€โ”€ start.ps1
```

## Local Setup

### 1. Install Dependencies

PowerShell:

```powershell
.\setup.ps1
```

Manual backend setup:

```powershell
cd backend
pip install -r requirements.txt
copy .env.example .env
```

Manual frontend setup:

```powershell
cd frontend
npm install
```

### 2. Configure Environment

Edit:

```text
backend/.env
```

Important values:

```env
ANTHROPIC_API_KEY=
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

### 3. Start the App

PowerShell:

```powershell
.\start.ps1
```

Manual backend:

```powershell
cd backend
uvicorn main:app --reload --port 8000
```

Manual frontend:

```powershell
cd frontend
npm run dev
```

Default URLs:

```text
Frontend: http://localhost:3000
Backend:  http://localhost:8000
API Docs: http://localhost:8000/docs
```

## Docker Compose

Set values in a root `.env` file, then run:

```powershell
docker compose up --build
```

Services:

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`

## Telegram Setup Summary

1. Create a bot with `@BotFather`.
2. Copy the bot token to `TELEGRAM_BOT_TOKEN`.
3. Set `TELEGRAM_BOT_USERNAME` to the bot username without `@`.
4. Add the bot as admin to the channel/group.
5. For group analytics, disable privacy mode in BotFather with `/setprivacy`.
6. Use `getUpdates` or `backend/get_group_id.py` to get private chat/group/channel IDs.
7. Register the webhook:

```bash
curl -X POST http://localhost:8000/telegram/webhook/register \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: <TELEGRAM_ADMIN_TOKEN>" \
  -d '{"webhook_url":"https://your-public-domain.com/telegram/webhook","drop_pending_updates":true}'
```

Webhook URL must be public HTTPS. Cloudflare Tunnel can be used for local testing.

Full instructions are in [docs/telegram-bot.md](docs/telegram-bot.md).

## Useful API Endpoints

### Health

```text
GET /health
```

### Telegram

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

### Predictions and Accuracy

```text
POST /analyze
GET  /predictions
GET  /predictions/{id}
POST /predictions/{id}/auto-compare
GET  /accuracy
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

## Security Notes

- The GitHub repo is private.
- `.env`, logs, local databases, `node_modules`, `.next`, and runtime tunnel files are ignored.
- Never commit real API keys, Telegram bot tokens, or admin tokens.
- Use `TELEGRAM_WEBHOOK_SECRET_TOKEN` to reject fake webhook requests.
- Use `TELEGRAM_ADMIN_TOKEN` for admin-only Telegram endpoints.

## Collaboration

For friends or teammates to access this private repository, invite their GitHub username as a collaborator from GitHub repository settings:

```text
Settings -> Collaborators -> Add people
```

Recommended permission for normal development is `Write`.

## Current Limitations

- Wallet checking currently identifies address type and returns explorer links. Balance and risk scoring need chain explorer API integration.
- Free vs paid content is split by sending different reports to different Telegram targets. It does not yet verify paid membership inside one shared group.
- News and IPO quality depends on configured RSS sources and manual `data/ipo_watchlist.json` entries.
