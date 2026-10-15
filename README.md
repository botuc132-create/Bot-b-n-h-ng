# MinhOS Telegram Bot + Mini App (Railway)

## What this package fixes
- Starts the Flask Mini App web server in a daemon thread when `python bot.py` starts.
- Web server binds to `0.0.0.0:$PORT` (default 8080) and exposes `/health`.
- Keeps bot and Mini App using the same SQLite `DB_PATH` and existing user/deposit/history tables.
- Keeps deposit confirmation manual by admin; opening a QR never credits balance.
- Purchase API intentionally remains disabled until inventory and delivery are implemented safely in the existing bot. It returns an error and does not debit the user's balance.

## Railway settings
1. Deploy this repository/root directory to the existing service that owns the bot source.
2. Start Command: `python bot.py` (or leave the `railway.json` start command in effect).
3. Public Networking target port: `8080` if your service's `PORT` variable is 8080. The app listens on `int(os.getenv("PORT", "8080"))`; Railway docs recommend listening on `0.0.0.0:$PORT`.
4. Set variables in Railway (never commit secrets):
   - `BOT_TOKEN`: current Telegram bot token (if a token appeared in logs/screenshots, revoke it in @BotFather and use a new one).
   - `WEBAPP_URL`: `https://worker-production-72e8.up.railway.app` (use the actual public domain assigned to this web service).
   - `ADMIN_IDS`: comma-separated numeric Telegram IDs allowed to use admin features.
   - `ADMIN_PASSWORD`: set a strong private value; do not rely on the source default.
   - `BANK_ID`, `BANK_ACCOUNT`, `BANK_ACCOUNT_NAME`, and optionally `ADMIN_CHAT_ID`.
   - `DB_PATH`: optional; preserve the existing path if you need to continue using the current SQLite database.
5. After deploy, open `https://worker-production-72e8.up.railway.app/health`. Expected JSON: `{"ok":true}`.
6. Open the bot and send `/start`; the `🌟 MỞ MINI APP` button appears if `WEBAPP_URL` begins with `https://`.

## Important operational cautions
- `409 Conflict` from Telegram `getUpdates` means another process is polling with the same bot token. Stop the old instance/duplicate Railway service or other host; run only one polling process for this token. Changing the web port does not fix this.
- This is still a single combined service. Do not also run `webapp.py` as a second bot service. It is imported by `bot.py` and started in a thread.
- SQLite data stored in a container filesystem may not survive redeploys unless it is on a persistent Railway Volume. Before changing `DB_PATH` or attaching/mounting a volume, back up and migrate the existing database carefully; changing the path creates a separate database and can make balances appear missing.
- Manual deposit confirmation is not automatic bank verification. Admins must verify bank receipt before pressing confirm.
- Purchase flow is deliberately disabled until real stock allocation and delivery, atomic debit/order creation, and duplicate-request protection are implemented. Do not advertise purchases as working yet.
- Mini App APIs require valid Telegram `initData`; opening the public URL directly in a browser will return 401 for protected API routes. `/health` is public for deployment checks.
