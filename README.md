# Bot bán tài khoản digital + duyệt đơn thủ công

Bot Telegram (aiogram) bán tài khoản digital theo luồng **Chọn sản phẩm → Chọn số lượng → Thanh toán QR → Admin duyệt**.
Hệ thống **tự sinh mã đơn ngẫu nhiên** (chuỗi chữ HOA + số, bỏ ký tự dễ nhầm) và sinh QR VietQR với nội dung CK thân thiện (vd `gui cafe K7QXM4P9RT`). Sau khi chuyển khoản, khách bấm **✅ Tôi đã chuyển khoản**; admin nhận thông báo kèm 2 nút **Chấp nhận / Từ chối** ngay trong Telegram. Chấp nhận → bot giao tài khoản (mỗi tài khoản là 1 dòng text trong kho). **Không dùng webhook, không lưu thông tin ngân hàng.**

## Tính năng
- Luồng mua hàng bằng nút bấm (inline keyboard) theo sản phẩm/số lượng.
- Sinh QR VietQR tự động qua `img.vietqr.io`, nội dung CK gồm lời nhắn thân thiện + mã đơn duy nhất.
- **Duyệt đơn thủ công**: khách báo đã CK → admin Chấp nhận/Từ chối qua nút inline; Chấp nhận giao hàng (hoặc chuyển chờ nâng cấp với SP nâng cấp chính chủ), Từ chối huỷ đơn + hoàn kho.
- Đơn chưa được duyệt **tự hết hạn** sau `ORDER_EXPIRY_MINUTES` phút và hoàn kho.
- Quản trị bằng **trang web** (bot chỉ còn 1 lệnh `/login`): quản lý sản phẩm, kho, xem đơn & doanh thu.

## Duyệt đơn thủ công
- Khách bấm **✅ Tôi đã chuyển khoản** trên màn QR → tất cả admin trong `ADMIN_IDS` nhận tin nhắn tóm tắt đơn (mã, sản phẩm, số tiền, khách, email nếu là đơn nâng cấp) kèm nút **Chấp nhận / Từ chối**.
- **Chấp nhận**: SP tài khoản → đánh dấu kho đã bán và gửi file `.txt` cho khách; SP nâng cấp chính chủ → chuyển trạng thái `awaiting_upgrade` để admin xử lý qua trang web.
- **Từ chối**: huỷ đơn (`expired`) + hoàn kho, báo khách đơn bị từ chối.
- Nút duyệt chống double-click: đơn đã xử lý/hết hạn sẽ báo "không còn ở trạng thái chờ".

## Cài đặt

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # rồi sửa các giá trị bên dưới
```

### Biến môi trường (`.env`)
| Biến | Ý nghĩa |
|------|---------|
| `BOT_TOKEN` | Token bot từ @BotFather |
| `ADMIN_IDS` | Telegram user id của admin, phẩy ngăn cách |
| `BANK_ACCOUNT` | Số tài khoản nhận tiền (sinh QR) |
| `BANK_CODE` | Mã ngân hàng VietQR/Napas (vd VietinBank=`ICB`, MBBank=`MB`) |
| `BANK_ACCOUNT_NAME` | Tên chủ TK (tuỳ chọn, hiển thị trên QR) |
| `PUBLIC_BASE_URL` | URL công khai (domain) để sinh link `/login` |
| `WEB_SECRET` | Khóa ký cookie/token phiên web admin |
| `ORDER_EXPIRY_MINUTES` | Thời gian đơn hết hạn nếu admin chưa duyệt (phút, mặc định 5) |
| `DATABASE_URL` | Mặc định `sqlite+aiosqlite:///bot.db` |

> ⚠️ **Bảo mật:** không commit file `.env`.

## Chạy

```bash
python -m bot.main
```

Lệnh trên chạy đồng thời: bot (long-polling) + web server (uvicorn) + tác vụ hết hạn đơn.

## Quản trị (web)
Trang quản trị là **SPA (Vite + Vue 3 + Naive UI)** trong thư mục `admin/`, phục vụ dưới `/admin/`. Backend cung cấp **JSON API** dưới `/admin/api`. Bot chỉ còn **1 lệnh admin duy nhất: `/login`**.

### Build admin SPA (bắt buộc trước khi chạy/deploy)
```bash
cd admin
npm install
npm run build   # xuất ra admin/dist (FastAPI tự phục vụ)
```
Dev nóng (tuỳ chọn): `npm run dev` (proxy `/admin/api` + `/admin/auth` về `127.0.0.1:8000`).

1. Trong Telegram gửi `/login` → bot trả về link `…/admin/auth?token=…` (hết hạn sau 1 giờ, chỉ admin trong `ADMIN_IDS` mới lấy được).
2. Mở link → trang web set cookie phiên (7 ngày) → vào trang quản trị tại `…/admin`.
3. Tại trang quản trị có thể: thêm sản phẩm, bật/tắt sản phẩm, **nạp tài khoản vào kho** (dán mỗi dòng 1 tài khoản), xem đơn gần đây và doanh thu, hoàn tất đơn nâng cấp.

Cần cấu hình `PUBLIC_BASE_URL` (domain) và `WEB_SECRET` trong `.env`.

## Kiểm thử

```bash
pip install -r requirements-dev.txt
pytest
```
Bộ test bao phủ: sinh mã đơn, QR VietQR, cấp phát kho, duyệt/từ chối đơn (`approve_order`/`reject_order`), idempotency, và trang admin.

## Deploy (VPS + domain, ví dụ thực tế)
Đang chạy tại **`https://ncp.danhtrong.online`** trên VPS Ubuntu (aaPanel/BT nginx):
- App chạy systemd service `botai` ở `127.0.0.1:8090` (`/opt/botai`, venv riêng).
- Nginx (BT) thêm vhost reverse-proxy `ncp.danhtrong.online` → `127.0.0.1:8090`, SSL Let's Encrypt (certbot webroot).
- Quản lý: `systemctl {status|restart} botai`, log: `journalctl -u botai -f`.
- Cập nhật code: **build admin SPA trước** (`cd admin && npm run build`), `rsync` lên `/opt/botai` (kèm `admin/dist`) rồi `systemctl restart botai`. `admin/dist` không commit vào git mà build khi deploy.

## Cấu trúc
```
bot/
  config.py            # cấu hình (.env)
  main.py              # entrypoint: polling + web server + expire loop
  db/                  # models, engine, repo
  services/            # payment (QR/mã đơn), orders (đơn + kho + duyệt), delivery, webauth
  handlers/            # user (luồng mua), admin (/login + nút Chấp nhận/Từ chối)
  keyboards.py, states.py, middlewares.py
webhook/
  server.py            # FastAPI: trang chủ + mount trang admin
  admin.py             # JSON API quản trị + phục vụ SPA (/admin, /admin/auth, ...)
tests/                 # pytest
```
