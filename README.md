# MinhOS Store Telegram Mini App (bản tích hợp an toàn theo mã nguồn được cung cấp)

## Phạm vi đã triển khai
- Giữ bot Python `python-telegram-bot==21.6`, database SQLite và các bảng hiện có; Mini App chạy cùng tiến trình Railway và đọc/ghi cùng DB_PATH.
- Mini App dùng Telegram Web Apps SDK; backend xác minh `initData` bằng BOT_TOKEN và không nhận user ID từ frontend.
- Hiển thị tài khoản/số dư, sản phẩm và giá từ `PRODUCTS` trong bot, lịch sử nạp/đơn hàng.
- Tạo yêu cầu nạp VietQR dùng cùng bảng `deposits`; gửi nút xác nhận/từ chối đến admin như luồng cũ. Chỉ xác nhận admin mới cộng tiền.
- Nút Tải file mở https://zalo.me/84338423525.
- API mua hàng hiện chủ động từ chối và KHÔNG trừ tiền: mã nguồn bot được cung cấp chưa có kho hàng thực, giao Key/tài khoản, hay cơ chế giữ hàng/hoàn tiền. Không thể tuyên bố luồng mua an toàn/hoàn chỉnh nếu thiếu các thành phần này.

## Railway — triển khai
1. Giải nén ZIP, đưa toàn bộ thư mục `minhios_railway_bot` vào GitHub repo của dự án bot hiện tại (không tạo bot/token mới). Kiểm tra kỹ thay đổi trước khi thay `bot.py`.
2. Railway → project/service hiện tại → Settings → Source, deploy repo/branch hiện tại. Build command để Railway tự cài `requirements.txt`; Start Command `python bot.py`.
3. Variables:
   - `BOT_TOKEN` = token của bot hiện tại (bí mật, chỉ ở backend)
   - `WEBAPP_URL` = URL HTTPS công khai của Railway service, ví dụ `https://ten-service.up.railway.app` (không có dấu `/` cuối)
   - `ADMIN_IDS` = Telegram numeric user ID admin, ví dụ `123456789` (nhiều ID cách nhau bằng dấu phẩy; bắt buộc cấu hình đúng)
   - `ADMIN_PASSWORD` = mật khẩu admin mạnh, khác mật khẩu mặc định cũ
   - `BANK_ID` = mã ngân hàng VietQR, ví dụ `ICB`
   - `BANK_ACCOUNT` = số tài khoản nhận tiền
   - `BANK_ACCOUNT_NAME` = tên chủ tài khoản đúng với ngân hàng
   - `ADMIN_CHAT_ID` = tùy chọn, ID chat nhận thông báo admin ngoài ADMIN_IDS
   - `DB_PATH` = nên để `/data/bot_data.sqlite3` nếu đã gắn Railway Volume tại `/data`; nếu chưa có volume, dùng `bot_data.sqlite3` nhưng dữ liệu có thể mất khi redeploy.
   - `ADMIN_USERNAME` = tên Telegram hỗ trợ, tùy chọn
4. Nếu dùng SQLite, tạo Railway Volume và mount tại `/data`, đặt `DB_PATH=/data/bot_data.sqlite3`. Nếu bot hiện tại đang dùng DB khác, phải giữ đúng đường dẫn và volume hiện có để không tạo DB trống/mất số dư. Không chạy hai bản bot polling đồng thời bằng cùng BOT_TOKEN.
5. Deploy. Mở domain `WEBAPP_URL/health`; cần trả JSON `{"ok":true}`. Mở Mini App bằng `/start` trong bot → nút “MỞ MINI APP”. Mini App không hoạt động đúng nếu mở URL trực tiếp trong trình duyệt ngoài Telegram vì thiếu `initData`.
6. Trong BotFather, có thể cấu hình Main Mini App/Menu Button nếu muốn: chọn bot → Bot Settings / Configure Mini App hoặc Menu Button (tên mục có thể thay đổi) → đặt URL HTTPS `WEBAPP_URL`. Nút Web App trong bàn phím bot đã được thêm sẵn.
7. Mỗi lần đổi URL/domain, cập nhật `WEBAPP_URL`, redeploy. Chỉ dùng HTTPS.

## Kiểm tra
- Mở Mini App từ Telegram: profile/số dư được lấy từ database chung.
- Tạo yêu cầu nạp: phải xuất hiện bản ghi pending và thông báo admin; số dư không đổi.
- Admin kiểm tra tài khoản ngân hàng rồi nhấn xác nhận trong bot: số dư tăng một lần; xác nhận lần nữa bị từ chối vì trạng thái không còn pending.
- Tạo QR hoặc bấm “đã chuyển khoản” không tự cộng tiền. Hiện chưa có xác minh ngân hàng tự động; muốn tự động phải tích hợp API/webhook ngân hàng.
- Giá và tên hiển thị lấy từ `PRODUCTS` trong `bot.py`.
- Mua hàng sẽ báo chưa cấu hình kho hàng và không trừ tiền. Để bật mua thực tế, cần bổ sung mô hình inventory/keys, trạng thái giao hàng và giao dịch nguyên tử trong DB trước khi cho phép debit.

## Lưu ý dữ liệu và bảo mật
- Backup database/volume trước deploy.
- Không commit `.env`, token hoặc thông tin bí mật vào GitHub.
- Bản bot nguồn có mật khẩu admin mặc định trong code (`huydz123`); hãy đặt `ADMIN_PASSWORD` mạnh ngay. Nên sửa tiếp để bỏ hẳn fallback mặc định và giới hạn quyền admin bằng `ADMIN_IDS`.
- Bản nguồn dùng SQLite. Không chia sẻ cùng một SQLite file qua nhiều service/replica; chạy một service duy nhất hoặc chuyển sang PostgreSQL và migrate dữ liệu có kiểm soát.
