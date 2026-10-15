# MinhOS Telegram Bot — VietQR fix

## Railway Variables
- `BOT_TOKEN`: Telegram bot token
- `ADMIN_IDS`: admin Telegram numeric user ID(s), comma-separated (required for admin permissions)
- `ADMIN_PASSWORD`: admin login password (change the default)
- `BANK_ID`: default `ICB`
- `BANK_ACCOUNT`: default `102886882160`
- `BANK_ACCOUNT_NAME`: exact account holder name (recommended)
- `ADMIN_CHAT_ID`: optional admin chat/user ID to receive deposit alerts if not already in `ADMIN_IDS`
- `ADMIN_USERNAME`: optional support username

## Commands
- `/start`: main menu
- `/nap 15000` or `/nap 15k`: create a deposit QR for the entered amount
- `/admin`: prompts for the admin password; after login, shows the admin panel

## Important
This version creates a VietQR request and alerts admins. It does not verify bank transfers automatically. Confirm a transfer in the actual bank account before pressing the admin confirmation button. Automatic verification requires a bank transaction API/webhook.

## Deploy
Replace the project files in Railway with these files and redeploy. Check Railway Deploy Logs for startup errors. Make sure only one running deployment/process is polling the same bot token.
