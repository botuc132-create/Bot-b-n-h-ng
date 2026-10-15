# MinhOS Telegram Bot — Railway

## Deploy
1. Đưa các file trong thư mục lên GitHub rồi deploy repository đó trên Railway.
2. Railway Variables cần có: `BOT_TOKEN`, `ADMIN_IDS` (Telegram numeric ID của admin), `ADMIN_CHAT_ID` (tuỳ chọn), `ADMIN_PASSWORD` (mặc định huydz123, nên đổi), `BANK_ID`, `BANK_ACCOUNT`, `BANK_ACCOUNT_NAME`.
3. Để giữ dữ liệu qua redeploy, gắn Railway Volume tại `/data` và đặt `DB_PATH=/data/bot_data.sqlite3`.
4. Khởi động bot bằng `/start`; gửi `/admin` để nhập mật khẩu.

## Nạp tiền
Bot tạo QR VietQR với đúng số tiền và nội dung chuyển khoản ngẫu nhiên, ghi đơn chờ và gửi thông báo cho Telegram ID admin đã cấu hình. Admin có nút xác nhận/từ chối. QR không tự xác minh tiền đã vào tài khoản. Muốn tự động cộng trong 1 phút cần tích hợp API/webhook của ngân hàng hoặc nhà cung cấp thanh toán, xác thực chữ ký webhook và đối soát giao dịch. Không tự cộng chỉ dựa trên ảnh chụp hoặc thao tác người dùng.

## Admin
Thống kê người dùng, tổng nạp đã xác nhận, đơn chờ, tổng số dư; cộng/trừ tiền; tra cứu UID, lịch sử nạp/mua/cộng trừ. Nên cấu hình `ADMIN_IDS` để giới hạn quyền admin; mật khẩu mặc định `huydz123` chỉ là bước đăng nhập đơn giản, hãy đổi ngay.

Các mức giá và tồn kho sản phẩm vẫn là dữ liệu mẫu. Chưa kết nối cổng thanh toán tự động, kho giao hàng tự động hoặc Mini App.


## Cấu hình QR nạp tiền trên Railway

Trong **Railway → project → service → Variables**, đặt các biến:

- `BOT_TOKEN`: token bot Telegram.
- `BANK_ID=ICB`
- `BANK_ACCOUNT=102886882160`
- `BANK_ACCOUNT_NAME`: tên chủ tài khoản đúng như ngân hàng (nếu muốn hiển thị trên QR).
- `ADMIN_IDS`: Telegram user ID admin, có thể nhập nhiều ID cách nhau bằng dấu phẩy.
- `ADMIN_PASSWORD`: nên đặt mật khẩu admin riêng, không dùng mật khẩu mặc định trong code.

Khi user nhập số tiền, bot tạo QR VietQR với số tiền và nội dung ngẫu nhiên, rồi gửi admin mã nội dung, số tiền, Telegram ID và thời gian tạo (GMT+7). Admin chỉ bấm **XÁC NHẬN ĐÃ NHẬN TIỀN** sau khi kiểm tra giao dịch thực tế trong tài khoản. QR tự nó không xác minh được tiền đã vào; muốn xác nhận/cộng tiền hoàn toàn tự động cần tích hợp API/webhook của ngân hàng hoặc nhà cung cấp đối soát.
