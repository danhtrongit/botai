# Thiết kế: Sản phẩm "nâng cấp chính chủ" + MBBank đăng nhập theo nhu cầu

Ngày: 2026-05-30

## Mục tiêu

1. **Sản phẩm nâng cấp chính chủ**: một số sản phẩm không giao tài khoản từ kho mà nâng cấp
   trực tiếp trên tài khoản của khách. Khách nhập **email** của họ; sau khi thanh toán, admin
   nâng cấp thủ công.
2. **Tối ưu MBBank**: chỉ đăng nhập & quét giao dịch khi có đơn chờ thanh toán, tránh giữ phiên
   liên tục gây khoá tài khoản.

## Quyết định đã chốt

- Thu email **trước khi thanh toán** (gắn vào đơn ngay).
- Khi tiền về cho đơn nâng cấp: **báo admin xử lý tay** (trạng thái `awaiting_upgrade`), admin bấm
  "Hoàn tất nâng cấp" trong web admin.
- Sản phẩm nâng cấp **cố định 1 email/đơn** (bỏ bước chọn số lượng).
- MBBank: **chỉ check khi có đơn chờ**; idle = không gọi MBBank, bỏ phiên đăng nhập.

## Data model

- `Product.kind: str` — `"account"` (mặc định) | `"upgrade"`.
  Migration: `ALTER TABLE products ADD COLUMN kind VARCHAR(20) NOT NULL DEFAULT 'account'`.
- `Order.buyer_email: str | None`.
  Migration: `ALTER TABLE orders ADD COLUMN buyer_email VARCHAR(255)`.
- Trạng thái đơn mới: `AWAITING_UPGRADE = "awaiting_upgrade"`.

## Luồng mua (bot)

- Sản phẩm `account`: giữ nguyên (chọn SL → QR → giao file TXT).
- Sản phẩm `upgrade`:
  - Bỏ qua kho & bước số lượng (qty = 1).
  - State mới `BuyFlow.entering_email`: bot hỏi "Nhập email cần nâng cấp", validate định dạng.
  - Tạo đơn với `buyer_email`, không reserve kho, total = price × 1 → hiện QR.

## Dịch vụ

- `orders.create_order(..., buyer_email=None)`:
  - Upgrade: không reserve kho; lưu email; vẫn sinh mã đơn + QR.
  - Account: như cũ.
  - Sau commit: gọi `poll_signal.signal_new_order()` để đánh thức MBBank poller.
- `orders.confirm_payment(...)`:
  - Đơn upgrade: `PENDING → PAID → AWAITING_UPGRADE`, không bán kho. Trả `PaymentResult` có
    `kind="upgrade"` để caller báo admin + nhắn khách "đang xử lý".
  - Đơn account: như cũ (`DELIVERED`).
- `delivery.notify_upgrade_pending(bot, order)`: nhắn khách "đang nâng cấp email X" + báo admin.
- `repo.count_pending_orders(session)`: đếm đơn `PENDING`.
- `repo.complete_upgrade(session, order)`: `AWAITING_UPGRADE → DELIVERED` (admin bấm nút).

## MBBank theo nhu cầu (`mbbank_poll.poll_loop`)

- `bot/services/poll_signal.py`: `wake = asyncio.Event()`, `signal_new_order()`, `wait_for_order()`.
- Vòng lặp:
  - Không có đơn pending → `_reset_client()` (bỏ phiên) → `await wake.wait()` (ngủ hẳn).
  - Có đơn pending → đăng nhập + quét → ngủ tới `interval` hoặc tới khi có đơn mới
    (`asyncio.wait_for(wake.wait(), timeout=interval)`).
- Idle: 0 lời gọi MBBank, không giữ login.

## Web admin

- Form thêm/sửa SP: chọn **Loại** (Tài khoản / Nâng cấp). Loại nâng cấp ẩn phần kho.
- Đơn hàng: hiện email + trạng thái `awaiting_upgrade`; nút "✅ Hoàn tất nâng cấp" → `DELIVERED`.

## Kiểm thử

- `create_order` upgrade: không động kho, lưu email, signal được set.
- `confirm_payment` upgrade: → `AWAITING_UPGRADE`, kho không đổi, reason/kind = upgrade.
- `count_pending_orders`, `complete_upgrade`.
- `poll_loop`: không có đơn pending → không gọi `_fetch_transactions_sync`.
- Email validation (hợp lệ / không hợp lệ).
- Admin: thêm SP upgrade, đơn upgrade hiện nút hoàn tất, bấm nút → delivered.
