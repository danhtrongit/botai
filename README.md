# Bot bán tài khoản digital + tự đối soát MBBank

Bot Telegram (aiogram) bán tài khoản digital theo luồng **Chọn sản phẩm → Chọn số lượng → Thanh toán QR**.
Hệ thống **tự sinh mã đơn (BOT…)** và **tự đối soát**: bot định kỳ đăng nhập MBBank (thư viện `mbbank-lib`), quét lịch sử giao dịch; khi thấy tiền vào khớp mã đơn → **tự động giao tài khoản** (mỗi tài khoản là 1 dòng text trong kho) cho khách. **Không dùng webhook.**

## Tính năng
- Luồng mua hàng bằng nút bấm (inline keyboard) theo sản phẩm/số lượng.
- Sinh QR VietQR tự động qua `img.vietqr.io`, nội dung CK là mã đơn duy nhất.
- Tự đối soát MBBank: quét giao dịch mỗi `MB_POLL_INTERVAL` giây, lọc tiền vào, **idempotent** theo `refNo`, đối soát số tiền, tự giao hàng.
- Đơn chưa thanh toán **tự hết hạn** và hoàn kho.
- Quản trị bằng **trang web** (bot chỉ còn 1 lệnh `/login`); nhập TK/MK MBBank trên web, **mã hoá Fernet khi lưu**.

## Đối soát qua MBBank (`bot/services/mbbank_poll.py`)
- Vào `/admin` nhập **tên đăng nhập + mật khẩu MBBank** (+ số TK, để trống thì tự dò TK đầu tiên). Lưu mã hoá bằng `ENCRYPTION_KEY` (Fernet) trong bảng `app_settings`.
- Vòng lặp nền (cạnh polling Telegram) gọi `getTransactionAccountHistory`; với mỗi giao dịch `creditAmount > 0`: lấy mã đơn `BOT…` trong `description`/`addDescription`, bỏ qua `refNo` đã xử lý, đối soát số tiền rồi giao hàng.
- Captcha MBBank tự giải bằng onnxruntime (đi kèm `mbbank-lib`).

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
| `ENCRYPTION_KEY` | Fernet key mã hoá TK/MK MBBank khi lưu (`Fernet.generate_key()`) |
| `MB_POLL_INTERVAL` | Chu kỳ quét giao dịch MBBank (giây, mặc định 25) |
| `PUBLIC_BASE_URL` | URL công khai (domain) để sinh link `/login` |
| `WEB_SECRET` | Khóa ký cookie/token phiên web admin |
| `ORDER_EXPIRY_MINUTES` | Thời gian đơn hết hạn (phút) |
| `DATABASE_URL` | Mặc định `sqlite+aiosqlite:///bot.db` |

> ⚠️ **Bảo mật:** không commit file `.env`.

## Chạy

```bash
python -m bot.main
```

Lệnh trên chạy đồng thời: bot (long-polling) + web server (uvicorn) + tác vụ hết hạn đơn + vòng lặp quét MBBank.

### Bật đối soát MBBank
1. Gửi `/login` trong Telegram → mở `/admin`.
2. Nhập **tên đăng nhập + mật khẩu MBBank** (+ số TK nếu muốn) → Lưu.
3. Bot bắt đầu quét giao dịch và tự giao hàng khi nhận đủ tiền.

## Quản trị (web)
Bot chỉ còn **1 lệnh admin duy nhất: `/login`**. Mọi thao tác quản trị thực hiện trên trang web.

1. Trong Telegram gửi `/login` → bot trả về link `…/admin/auth?token=…` (hết hạn sau 1 giờ, chỉ admin trong `ADMIN_IDS` mới lấy được).
2. Mở link → trang web set cookie phiên (7 ngày) → vào trang quản trị tại `…/admin`.
3. Tại trang quản trị có thể: thêm sản phẩm, bật/tắt sản phẩm, **nạp tài khoản vào kho** (dán mỗi dòng 1 tài khoản), **cấu hình TK/MK MBBank**, xem đơn gần đây và doanh thu.

Cần cấu hình `PUBLIC_BASE_URL` (domain) và `WEB_SECRET` trong `.env`.

## Kiểm thử

```bash
pip install -r requirements-dev.txt
pytest
```
Bộ test bao phủ: sinh/đối soát mã đơn, QR VietQR, cấp phát kho, idempotency, mã hoá TK/MK (Fernet), đối soát giao dịch MBBank (`process_transactions`), và trang admin. Test không cần `mbbank-lib` (import trễ).

## Deploy (VPS + domain, ví dụ thực tế)
Đang chạy tại **`https://ncp.danhtrong.online`** trên VPS Ubuntu (aaPanel/BT nginx):
- App chạy systemd service `botai` ở `127.0.0.1:8090` (`/opt/botai`, venv riêng).
- Nginx (BT) thêm vhost reverse-proxy `ncp.danhtrong.online` → `127.0.0.1:8090`, SSL Let's Encrypt (certbot webroot).
- Quản lý: `systemctl {status|restart} botai`, log: `journalctl -u botai -f`.
- Cập nhật code: `rsync` lên `/opt/botai` rồi `systemctl restart botai`.

## Cấu trúc
```
bot/
  config.py            # cấu hình (.env)
  main.py              # entrypoint: polling + webhook + expire loop
  db/                  # models, engine, repo
  services/            # sepay (QR/đối soát), orders (đơn + kho), delivery, webauth (token web)
  handlers/            # user (luồng mua), admin (chỉ /login)
  keyboards.py, states.py, middlewares.py
webhook/
  server.py            # FastAPI: POST /sepay/webhook + mount trang admin
  admin.py             # trang quản trị web (/admin, /admin/auth, ...)
tests/                 # pytest
```
