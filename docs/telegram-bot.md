# Telegram Bot System

This backend now supports the three requested Telegram modes:

1. One-way Telegram channel updates for market news, watchlist assets, and IPO agenda.
2. Private Telegram bot chat with commands and natural-language intent matching.
3. Free community updates with limited public data, plus a paid chat/channel target for full reports.

The dashboard at `http://localhost:3000/telegram` shows weekly topics, intents, keywords, message volume, and recent messages from private chats and Telegram groups.

## 1. Create and prepare the bot

1. Open Telegram and chat with `@BotFather`.
2. Run `/newbot` and copy the bot token.
3. Run `/setprivacy` and choose `Disable` if you want the bot to collect all group/community messages for analytics. If privacy mode stays enabled, Telegram only sends commands, replies, and mentions to the bot.
4. Add the bot as an admin to the channel and the community group/supergroup.
5. Set `TELEGRAM_BOT_USERNAME` to the bot username without `@`, for example `AgentInvestBot`.

## 2. Configure backend env

For local PowerShell startup, edit `backend/.env`:

```env
TELEGRAM_BOT_TOKEN=123456:replace_me
TELEGRAM_BOT_USERNAME=AgentInvestBot

# One-way channel broadcast target
TELEGRAM_CHANNEL_ID=@your_channel
TELEGRAM_DAILY_REPORT_ENABLED=true

# Free community target. This receives limited public previews.
TELEGRAM_COMMUNITY_CHAT_ID=-1001234567890
TELEGRAM_COMMUNITY_REPORT_ENABLED=true

# Paid/subscriber target. This receives the full report.
TELEGRAM_PAID_CHAT_ID=-1009876543210
TELEGRAM_PAID_REPORT_ENABLED=true

# Webhook/admin safety
TELEGRAM_WEBHOOK_SECRET_TOKEN=make-a-random-secret
TELEGRAM_ADMIN_TOKEN=make-an-admin-token

TELEGRAM_DAILY_REPORT_HOUR=8
TELEGRAM_DAILY_REPORT_MINUTE=30
TELEGRAM_TIMEZONE=Asia/Bangkok
TELEGRAM_USE_AI_SUMMARY=true
TELEGRAM_PUBLIC_NEWS_LIMIT=3
TELEGRAM_PUBLIC_WATCHLIST_LIMIT=3
TELEGRAM_PRIVATE_REPORT_MAX_ASSETS=8
TELEGRAM_PRIVATE_REPORT_MAX_NEWS_ITEMS=20

MONITOR_WATCHLIST_SYMBOLS=AAPL,MSFT,NVDA,TSLA,SPY,QQQ,BTC-USD,ETH-USD
MONITOR_IPO_WATCHLIST_PATH=../data/ipo_watchlist.json
```

For Docker Compose, set the same values in the root `.env`. The compose file maps `./data` to `/app/data` and uses `/app/data/ipo_watchlist.json`.

## 3. Register the webhook

The webhook URL must be public HTTPS, for example a Cloudflare Tunnel URL:

```text
https://your-public-host.example.com/telegram/webhook
```

Register it from FastAPI docs or with curl:

```bash
curl -X POST http://localhost:8000/telegram/webhook/register \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: make-an-admin-token" \
  -d '{"webhook_url":"https://your-public-host.example.com/telegram/webhook","drop_pending_updates":true}'
```

Useful webhook endpoints:

- `POST /telegram/webhook/register` sets the Telegram webhook.
- `GET /telegram/webhook/info` checks webhook status.
- `POST /telegram/webhook/delete` removes the webhook.
- `POST /telegram/webhook` receives Telegram updates. Telegram calls this endpoint directly.

If `TELEGRAM_WEBHOOK_SECRET_TOKEN` is set, Telegram will send `X-Telegram-Bot-Api-Secret-Token` and the backend rejects mismatches.

## 4. Private chat commands and natural language

Supported commands:

- `/news` sends noteworthy market news.
- `/watchlist` sends assets to monitor.
- `/ipo` sends IPO agenda.
- `/ipohk` sends Hong Kong IPO agenda.
- `/checkaddress <wallet>` identifies EVM, Bitcoin, Tron, or Solana-style addresses and returns explorer links.
- `/report` sends the full daily monitor.
- `/help` lists commands.

Natural language examples also work:

```text
อยากดู IPO ฮ่องกง
หุ้นที่ควรติดตามวันนี้
อยากตรวจกระเป๋าคริปโต 0x0000000000000000000000000000000000000000
ขอข่าวที่น่าจับตา
```

The matcher is keyword/rule based and logs every incoming message with `intent`, `topic`, and extracted keywords for weekly analytics.

## 5. Community and paid content

Scheduled sending uses one daily time window:

- `TELEGRAM_DAILY_REPORT_ENABLED=true` sends the full report to `TELEGRAM_CHANNEL_ID`.
- `TELEGRAM_COMMUNITY_REPORT_ENABLED=true` sends a limited public preview to `TELEGRAM_COMMUNITY_CHAT_ID`.
- `TELEGRAM_PAID_REPORT_ENABLED=true` sends the full report to `TELEGRAM_PAID_CHAT_ID`.

Manual broadcast endpoint:

```json
POST /telegram/broadcast
{
  "target": "community",
  "public_preview": true,
  "use_ai": false
}
```

Targets are `channel`, `community`, or `paid`. You can also pass `chat_id` directly for a one-off target.

## 6. Analytics dashboard

Open:

```text
http://localhost:3000/telegram
```

Backend endpoint:

```text
GET /telegram/analytics?days=7&limit=10
```

Tracked fields include:

- total private/community messages
- unique users and active chats
- top topics and intents
- top keywords
- recent messages
- daily private vs group message trend

## 7. IPO watchlist format

Edit `data/ipo_watchlist.json` when you want guaranteed reminders for IPOs that may not appear in RSS/news sources:

```json
[
  {
    "company": "Company Name",
    "symbol": "TICKER",
    "exchange": "HKEX",
    "expected_date": "2026-07-09",
    "status": "prospectus_review",
    "summary": "Short prospectus note or reason to monitor.",
    "link": "https://example.com/prospectus.pdf",
    "source": "manual_watchlist"
  }
]
```

## 8. Operational notes

- The bot must remain admin in channels/groups it posts to.
- Telegram group analytics require BotFather privacy mode disabled.
- This system separates free and paid content by sending different report versions to different Telegram targets. It does not yet verify payment/subscription status inside one shared group.
- Wallet checking currently identifies address type and returns explorer links. Balance/risk scoring can be added with chain explorer APIs later.
- Reports are stored in `monitor_reports`; Telegram user/chat/message analytics are stored in `telegram_users`, `telegram_chats`, and `telegram_messages`.
