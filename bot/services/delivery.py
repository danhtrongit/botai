from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile

from bot import keyboards
from bot.config import get_settings
from bot.db.models import Order

logger = logging.getLogger(__name__)


def _order_summary(order: Order, *, is_upgrade: bool) -> str:
    """Tóm tắt đơn để hiển thị cho admin."""
    buyer = f"<code>{order.buyer_tg_id}</code>"
    if order.buyer_username:
        buyer += f" (@{order.buyer_username})"
    lines = [
        f"Mã đơn: <code>{order.code}</code>",
        f"Sản phẩm: #{order.product_id} · SL {order.quantity}",
        f"Số tiền: <b>{order.total_amount:,}đ</b>",
        f"Khách: {buyer}",
    ]
    if is_upgrade:
        lines.append(f"Email nâng cấp: <code>{order.buyer_email or '(chưa có)'}</code>")
    return "\n".join(lines)


async def notify_admins_review(bot: Bot, order: Order, *, is_upgrade: bool) -> None:
    """Khách báo đã chuyển khoản -> gửi admin đơn kèm nút Chấp nhận / Từ chối."""
    settings = get_settings()
    text = (
        "🔔 <b>ĐƠN CHỜ DUYỆT</b> (khách báo đã chuyển khoản)\n"
        f"{_order_summary(order, is_upgrade=is_upgrade)}\n\n"
        "Kiểm tra tài khoản nhận tiền rồi bấm <b>Chấp nhận</b> để giao hàng, "
        "hoặc <b>Từ chối</b> để huỷ đơn."
    )
    markup = keyboards.admin_review_keyboard(order.id)
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=markup)
        except TelegramAPIError as exc:
            logger.error("Gửi đơn %s cho admin %s thất bại: %s", order.code, admin_id, exc)


async def deliver(bot: Bot, order: Order, payloads: list[str]) -> bool:
    """Gửi tài khoản cho khách dưới dạng FILE .txt đính kèm. Trả True nếu thành công.

    Gửi file thay vì tin nhắn để tránh lỗi parse HTML khi nội dung tài khoản
    chứa ký tự đặc biệt (vd <...>), đồng thời gọn gàng khi số lượng lớn.
    """
    content = "\n".join(payloads) + "\n"
    document = BufferedInputFile(content.encode("utf-8"), filename=f"{order.code}.txt")
    # Caption chỉ chứa mã đơn (an toàn HTML); nội dung tài khoản nằm trong file.
    caption = (
        f"✅ Thanh toán đơn <code>{order.code}</code> thành công!\n"
        f"📎 {len(payloads)} tài khoản của bạn nằm trong file đính kèm.\n"
        f"Cảm ơn bạn đã mua hàng! 🎉"
    )
    try:
        await bot.send_document(order.buyer_tg_id, document=document, caption=caption)
        return True
    except TelegramAPIError as exc:
        logger.error("Giao hàng đơn %s thất bại: %s", order.code, exc)
        await _notify_admins_delivery_failed(bot, order, exc)
        return False


async def notify_upgrade_pending(bot: Bot, order: Order) -> None:
    """Đơn nâng cấp chính chủ đã thanh toán: báo khách đang xử lý + báo admin nâng cấp tay."""
    email = order.buyer_email or "(chưa có email)"
    try:
        await bot.send_message(
            order.buyer_tg_id,
            f"✅ Đã nhận thanh toán đơn <code>{order.code}</code>!\n"
            f"🛠 Đang nâng cấp chính chủ cho email <code>{email}</code>.\n"
            f"Quá trình thường hoàn tất trong ít phút. Bạn sẽ nhận thông báo khi xong.\n\n"
            f"🆘 Cần hỗ trợ? Liên hệ @ncp_ai",
        )
    except TelegramAPIError as exc:
        logger.error("Báo khách đơn nâng cấp %s thất bại: %s", order.code, exc)

    settings = get_settings()
    admin_text = (
        f"🛠 <b>ĐƠN NÂNG CẤP cần xử lý</b>\n"
        f"Mã đơn: <code>{order.code}</code>\n"
        f"Email: <code>{email}</code>\n"
        f"Khách: <code>{order.buyer_tg_id}</code>"
        f"{(' (@' + order.buyer_username + ')') if order.buyer_username else ''}\n"
        f"Số tiền: {order.total_amount:,}đ\n\n"
        f"Vào /admin → Đơn hàng để bấm 'Hoàn tất nâng cấp' sau khi xong."
    )
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, admin_text)
        except TelegramAPIError:
            pass


async def _notify_admins_delivery_failed(bot: Bot, order: Order, exc: Exception) -> None:
    settings = get_settings()
    text = (
        f"⚠️ Đơn <code>{order.code}</code> đã thanh toán nhưng GIAO HÀNG LỖI "
        f"(user {order.buyer_tg_id}). Vào /admin xem chi tiết đơn để giao thủ công."
    )
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except TelegramAPIError:
            pass
