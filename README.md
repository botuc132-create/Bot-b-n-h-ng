# MinhOS Telegram Bot (Railway)

## Chạy trên Railway
1. Tải giải nén thư mục này, đưa các file lên GitHub repository.
2. Trên Railway chọn **New Project → Deploy from GitHub Repo** và chọn repository.
3. Vào **Variables** của service, thêm `BOT_TOKEN` = token bot lấy từ BotFather.
4. Deploy. Railway sẽ chạy worker bằng `python bot.py`.

## Lưu ý
- Bot dùng Inline Keyboard cho tất cả menu, không dùng ReplyKeyboardMarkup.
- Đây là bản giao diện mẫu. Giá/tồn kho đang là dữ liệu minh họa; các chức năng thanh toán, giao hàng, tải file và Mini App chưa được kết nối.
- SQLite lưu trong filesystem của container. Để giữ dữ liệu qua lần deploy/restart, hãy gắn Railway Volume và đặt biến `DB_PATH` vào đường dẫn nằm trên volume, ví dụ `/data/bot_data.sqlite3`.
- Không đưa BOT_TOKEN lên GitHub hoặc gửi công khai.
