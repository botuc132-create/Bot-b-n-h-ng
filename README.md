# MinhOS Store Bot + Mini App (Railway)

## Chức năng đã thêm
- Nút **MỞ MINI APP** trong menu `/start` và nút menu Mini App ở góc dưới bên trái Telegram (khi `WEBAPP_URL` là HTTPS).
- Mini App giao diện tối, cửa hàng chia sản phẩm/gói, ảnh thu nhỏ, giá và số key còn trong kho.
- Admin trong Mini App: hỏi mật khẩu, thêm sản phẩm cùng ảnh nhỏ, nhập nhiều key mỗi dòng, thêm key vào sản phẩm, sửa giá, xóa/ẩn sản phẩm và xem lịch sử người mua.
- Mua hàng dùng chung SQLite với bot: kiểm tra số dư và tồn kho, trừ tiền trong transaction, cấp một key còn trong kho và ghi lịch sử. Key đã bán được đánh dấu `sold` nên không thể bán lần hai.
- Bot và Mini App dùng chung `DB_PATH`; danh mục/key được lưu trong SQLite. Admin có nút mở khu vực quản lý sản phẩm Mini App ngay trong menu `/admin`; bot shop đọc cùng danh mục/kho và mua hàng cũng cấp key từ cùng kho.
- Lịch sử người mua hiển thị Telegram ID, username, sản phẩm, giá, thời gian và key đã cấp (chỉ admin).

## Triển khai Railway
1. Giải nén ZIP, đưa toàn bộ nội dung thư mục này lên GitHub repository.
2. Tạo/ chọn Railway service kết nối repo đó. Start Command: `python bot.py`.
3. Bật **Public Networking** cho service, dùng cổng Railway được cấp qua biến `PORT`. `webapp.py` tự lắng nghe `0.0.0.0:$PORT`.
4. Thêm Variables trong Railway:
   - `BOT_TOKEN` = token bot Telegram.
   - `WEBAPP_URL` = URL HTTPS công khai của service, ví dụ `https://ten-service.up.railway.app` (thay bằng domain thực).
   - `ADMIN_IDS` = Telegram user ID dạng số, ví dụ `123456789`. Có thể nhiều ID, cách nhau dấu phẩy.
   - `ADMIN_PASSWORD` = `Huydz123` theo yêu cầu (nên đổi thành mật khẩu riêng tư mạnh trước khi dùng thật).
   - `BANK_ID`, `BANK_ACCOUNT`, `BANK_ACCOUNT_NAME` = thông tin ngân hàng nếu dùng nạp tiền QR.
   - `ADMIN_CHAT_ID` = tùy chọn, ID nhận thông báo yêu cầu nạp.
   - `DB_PATH` = tùy chọn; nếu dùng Railway Volume, đặt đường dẫn DB vào mount path của Volume, ví dụ `/data/bot_data.sqlite3`.
5. Deploy và mở `https://<domain-cua-ban>/health`; cần nhận `{"ok":true}`.
6. Mở bot Telegram, gửi `/start`, nhấn **MỞ MINI APP** hoặc nút menu Mini App.
7. Admin mở Mini App, nhấn **Admin** và nhập `Huydz123`. Telegram ID của tài khoản phải nằm trong `ADMIN_IDS`.
8. Vào Admin → thêm sản phẩm, chọn loại, nhập tên gói/giá, chọn ảnh nhỏ (tối đa 1 MB), dán key mỗi dòng rồi bấm thêm. Ví dụ:
   ```
   TRLL-AEBE-D79A-E394
   TRLL-C0AB-0DD8-F13F
   ```
   Hệ thống báo số key đã thêm. Khi khách mua thành công, một key chuyển sang trạng thái đã bán và được ghi vào lịch sử người mua.

## Lưu ý quan trọng
- **Phải dùng Railway Volume cho SQLite** nếu muốn dữ liệu còn sau các lần redeploy/restart. Không đổi `DB_PATH` sang file mới nếu cần giữ số dư và lịch sử hiện tại; hãy sao lưu/migrate DB trước.
- Chỉ một tiến trình chạy polling với cùng `BOT_TOKEN`; nếu thấy `409 Conflict`, hãy tắt instance bot trùng lặp.
- Mini App cần mở từ Telegram để có `initData` hợp lệ; mở URL trực tiếp trên trình duyệt sẽ không đăng nhập được API.
- `ADMIN_IDS` là lớp phân quyền bắt buộc cho quản trị Mini App. Đừng để trống biến này.
- Nạp tiền QR vẫn cần admin kiểm tra tiền thực vào ngân hàng rồi xác nhận; QR không tự xác minh giao dịch.
- Giá trị tồn kho được tính từ key thực trong kho, không phải số lượng ghi trong tên gói.
