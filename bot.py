import os
import logging
import sqlite3
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "bot_data.sqlite3")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO
)
log = logging.getLogger("minhios_bot")

PRODUCTS = {
    "innova": {
        "name": "🗃 iNNOVA Cheat",
        "plans": [
            {"label": "1 Ngày • 20.000đ • CÒN 10", "price": 20000, "stock": 10},
            {"label": "7 Ngày • HẾT HÀNG", "price": 70000, "stock": 0},
            {"label": "30 Ngày • HẾT HÀNG", "price": 200000, "stock": 0},
        ],
    },
    "aim": {"name": "🧟 Aim Hack - iOS/Android", "plans": [
        {"label": "1 Ngày • 20.000đ • CÒN 10", "price": 20000, "stock": 10},
        {"label": "7 Ngày • HẾT HÀNG", "price": 70000, "stock": 0},
        {"label": "30 Ngày • HẾT HÀNG", "price": 200000, "stock": 0},
    ]},
    "migul_lite": {"name": "🎮 Migul AOV Lite", "plans": [
        {"label": "1 Ngày • 20.000đ • CÒN 10", "price": 20000, "stock": 10},
        {"label": "7 Ngày • HẾT HÀNG", "price": 70000, "stock": 0},
        {"label": "30 Ngày • HẾT HÀNG", "price": 200000, "stock": 0},
    ]},
    "boxvip": {"name": "👑 Box ViP iMZ-Filza", "plans": [
        {"label": "1 Ngày • 20.000đ • CÒN 10", "price": 20000, "stock": 10},
        {"label": "7 Ngày • HẾT HÀNG", "price": 70000, "stock": 0},
        {"label": "30 Ngày • HẾT HÀNG", "price": 200000, "stock": 0},
    ]},
    "aimkill": {"name": "📱 iPA Aimkill Đình Hoàng", "plans": [
        {"label": "1 Ngày • 20.000đ • CÒN 10", "price": 20000, "stock": 10},
        {"label": "7 Ngày • HẾT HÀNG", "price": 70000, "stock": 0},
        {"label": "30 Ngày • HẾT HÀNG", "price": 200000, "stock": 0},
    ]},
    "drip": {"name": "🟣 Drip Wire - iOS/Android", "plans": [
        {"label": "1 Ngày • 20.000đ • CÒN 10", "price": 20000, "stock": 10},
        {"label": "7 Ngày • HẾT HÀNG", "price": 70000, "stock": 0},
        {"label": "30 Ngày • HẾT HÀNG", "price": 200000, "stock": 0},
    ]},
    "flork_external": {"name": "🐵 iPA Flork External", "plans": [
        {"label": "1 Ngày • 20.000đ • CÒN 10", "price": 20000, "stock": 10},
        {"label": "7 Ngày • HẾT HÀNG", "price": 70000, "stock": 0},
        {"label": "30 Ngày • HẾT HÀNG", "price": 200000, "stock": 0},
    ]},
    "flork_tipa": {"name": "🐵 Flork TiPA (iOS14-16.7.16)", "plans": [
        {"label": "1 Ngày • 20.000đ • CÒN 10", "price": 20000, "stock": 10},
        {"label": "7 Ngày • HẾT HÀNG", "price": 70000, "stock": 0},
        {"label": "30 Ngày • HẾT HÀNG", "price": 200000, "stock": 0},
    ]},
    "migul_pro": {"name": "🎮 Migul AOV Pro", "plans": [
        {"label": "1 Ngày • 20.000đ • CÒN 10", "price": 20000, "stock": 10},
        {"label": "7 Ngày • HẾT HÀNG", "price": 70000, "stock": 0},
        {"label": "30 Ngày • HẾT HÀNG", "price": 200000, "stock": 0},
    ]},
    "migul_basic": {"name": "📱 Migul Basic - VietNam Version", "plans": [
        {"label": "1 Ngày • 20.000đ • CÒN 10", "price": 20000, "stock": 10},
        {"label": "7 Ngày • HẾT HÀNG", "price": 70000, "stock": 0},
        {"label": "30 Ngày • HẾT HÀNG", "price": 200000, "stock": 0},
    ]},
}
APPS = [
    ("innova", "🟢 iNNOVA Cheat"),
    ("aim", "🧟 Aim Hack - iOS/Android"),
    ("migul_lite", "🎮 Migul AOV Lite"),
    ("boxvip", "👑 Box ViP iMZ-Filza"),
    ("aimkill", "📱 iPA Aimkill Đình Hoàng"),
    ("drip", "🟣 Drip Wire - iOS/Android"),
    ("flork_external", "🐵 iPA Flork External"),
    ("flork_tipa", "🐵 Flork TiPA (iOS14-16.7.16)"),
    ("migul_pro", "🎮 Migul AOV Pro"),
    ("migul_basic", "📱 Migul Basic - VietNam Version"),
]

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0,
        total_deposit INTEGER DEFAULT 0, created_at TEXT
    )""")
    conn.commit()
    return conn

def ensure_user(user):
    with db() as conn:
        conn.execute(
            "INSERT INTO users(user_id, username, created_at) VALUES(?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username",
            (user.id, user.username or "", datetime.utcnow().isoformat())
        )

def get_user(user_id):
    with db() as conn:
        row = conn.execute(
            "SELECT user_id, username, balance, total_deposit FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()
    return row or (user_id, "", 0, 0)

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 TÀI KHOẢN", callback_data="account"),
         InlineKeyboardButton("🛍 CỬA HÀNG", callback_data="shop")],
        [InlineKeyboardButton("💰 NẠP TIỀN", callback_data="deposit"),
         InlineKeyboardButton("📊 LỊCH SỬ", callback_data="history")],
        [InlineKeyboardButton("📥 TẢI FILE", callback_data="files"),
         InlineKeyboardButton("💬 HỖ TRỢ", callback_data="support")],
        [InlineKeyboardButton("🌟 MỞ MINI APP", callback_data="miniapp")],
    ])

def back_keyboard(target="home"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("QUAY LẠI", callback_data=target)]])

async def show(query, text, keyboard):
    await query.answer()
    try:
        await query.edit_message_text(text=text, reply_markup=keyboard)
    except Exception:
        await query.message.reply_text(text=text, reply_markup=keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)
    text = (
        "Chào Mừng Đến Với Bot MinhOS - Store Hack Auto Bán Hàng Tự Động 24/7\n\n"
        "📢 Kênh thông báo: @minhiosbanhacks1\n"
        "🌨 Admin: @minhiosne\n"
        "━━━━━━━━━━━━━━\n"
        "📌 Tổng nạp: 0đ\n"
        "🏅 Tổng nạp tháng: 0đ\n"
        "🏦 Số dư: 0đ\n\n"
        "Vui lòng chọn chức năng bên dưới."
    )
    await update.message.reply_text(text, reply_markup=main_keyboard())

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    user = update.effective_user
    ensure_user(user)

    if data == "home":
        await show(q, "🏠 MENU CHÍNH\n\nVui lòng chọn chức năng:", main_keyboard())
    elif data == "account":
        uid, username, balance, total = get_user(user.id)
        text = (
            "👤 THÔNG TIN CÁ NHÂN\n\n"
            f"🆔 UID: {uid}\n"
            f"🍊 Username: @{username if username else 'chưa_có_username'}\n"
            f"💰 Số dư: {balance:,}đ\n"
            "🌐 Ngôn ngữ: TIẾNG VIỆT 🇻🇳"
        )
        await show(q, text, back_keyboard())
    elif data == "shop":
        text = "🛍 CỬA HÀNG\n\nChọn mục bạn muốn mua:"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 MUA KEY", callback_data="buy_key")],
            [InlineKeyboardButton("🛍 MUA TÀI KHOẢN", callback_data="buy_account")],
            [InlineKeyboardButton("QUAY LẠI", callback_data="home")],
        ])
        await show(q, text, keyboard)
    elif data in ("buy_account", "buy_key"):
        title = "📱 CHỌN ỨNG DỤNG" if data == "buy_account" else "🔑 CHỌN LOẠI KEY"
        rows = [[InlineKeyboardButton(label, callback_data=f"app:{key}")] for key, label in APPS]
        rows.append([InlineKeyboardButton("QUAY LẠI", callback_data="shop")])
        await show(q, title + "\n\nChọn sản phẩm bạn muốn mua:", InlineKeyboardMarkup(rows))
    elif data.startswith("app:"):
        key = data.split(":", 1)[1]
        product = PRODUCTS.get(key)
        if not product:
            await show(q, "Không tìm thấy sản phẩm.", back_keyboard("buy_account"))
            return
        rows = []
        for i, plan in enumerate(product["plans"]):
            label = plan["label"]
            callback = f"plan:{key}:{i}" if plan["stock"] > 0 else "soldout"
            rows.append([InlineKeyboardButton(label, callback_data=callback)])
        rows.append([InlineKeyboardButton("QUAY LẠI", callback_data="buy_account")])
        await show(q, f"{product['name']}\n\nChọn gói bạn muốn mua:", InlineKeyboardMarkup(rows))
    elif data.startswith("plan:"):
        _, key, idx = data.split(":")
        plan = PRODUCTS[key]["plans"][int(idx)]
        if plan["stock"] < 1:
            await show(q, "❌ Gói này hiện đã hết hàng.", back_keyboard(f"app:{key}"))
            return
        # Demo only: do not deduct balance or claim a purchase without payment/order backend.
        text = (
            f"🛒 XÁC NHẬN GÓI\n\n{PRODUCTS[key]['name']}\n"
            f"Gói: {plan['label']}\nGiá: {plan['price']:,}đ\n\n"
            "Đây là giao diện mẫu. Cần cấu hình thanh toán và kho hàng thật trước khi bán."
        )
        await show(q, text, InlineKeyboardMarkup([
            [InlineKeyboardButton("QUAY LẠI", callback_data=f"app:{key}")],
            [InlineKeyboardButton("VỀ CỬA HÀNG", callback_data="shop")],
        ]))
    elif data == "soldout":
        await show(q, "❌ Gói này hiện đã hết hàng.", back_keyboard("buy_account"))
    elif data == "deposit":
        await show(q, "💰 NẠP TIỀN\n\nChức năng nạp tiền chưa được kết nối cổng thanh toán. Vui lòng liên hệ admin @minhiosne.", back_keyboard())
    elif data == "history":
        await show(q, "📊 LỊCH SỬ\n\nChưa có giao dịch nào.", back_keyboard())
    elif data == "files":
        await show(q, "📥 TẢI FILE\n\nChưa cấu hình file tải xuống. Vui lòng liên hệ admin.", back_keyboard())
    elif data == "support":
        await show(q, "💬 HỖ TRỢ\n\nLiên hệ admin: @minhiosne", back_keyboard())
    elif data == "miniapp":
        await show(q, "🌟 MINI APP\n\nChưa cấu hình WEBAPP_URL. Khi có website, thêm nút Web App với URL HTTPS của bạn.", back_keyboard())
    else:
        await show(q, "Chức năng chưa được cấu hình.", back_keyboard())

async def post_init(app: Application):
    # Start-up DB check
    with db():
        pass
    log.info("Database initialized")

def main():
    if not TOKEN:
        raise RuntimeError("Thiếu biến môi trường BOT_TOKEN. Hãy thêm BOT_TOKEN trong Railway Variables.")
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    log.info("Bot is starting with polling")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
