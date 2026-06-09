from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings
from bot.db import models, repo
from bot.db.database import async_session
from bot.middlewares import AdminOnlyMiddleware
from bot.services import delivery, webauth
from bot.services import orders as order_service

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.middleware(AdminOnlyMiddleware())
router.callback_query.middleware(AdminOnlyMiddleware())


@router.message(Command("login"))
async def cmd_login(message: Message) -> None:
    """Lệnh admin DUY NHẤT: cấp link đăng nhập trang quản trị web."""
    settings = get_settings()
    if not settings.public_base_url:
        await message.answer(
            "⚠️ Chưa cấu hình <code>PUBLIC_BASE_URL</code> nên chưa tạo được link quản trị."
        )
        return
    token = webauth.make_token(message.from_user.id)
    url = f"{settings.public_base_url.rstrip('/')}/admin/auth?token={token}"
    await message.answer(
        "🔐 <b>Liên kết quản trị</b> (hết hạn sau 1 giờ, chỉ dùng cho bạn):\n"
        f"{url}\n\n"
        "Mở link để thêm sản phẩm, nạp tài khoản, xem đơn & doanh thu.",
        disable_web_page_preview=True,
    )


async def _strip_review_buttons(callback: CallbackQuery, suffix: str) -> None:
    """Bỏ nút Chấp nhận/Từ chối và ghi chú kết quả vào tin nhắn admin."""
    try:
        await callback.message.edit_text(
            (callback.message.html_text or callback.message.text or "") + f"\n\n{suffix}",
            reply_markup=None,
        )
    except Exception:  # noqa: BLE001 — chỉnh sửa tin nhắn là phụ, lỗi thì bỏ qua
        pass


@router.callback_query(lambda c: c.data and c.data.startswith("adm_ok:"))
async def cb_admin_approve(callback: CallbackQuery) -> None:
    """Admin Chấp nhận đơn -> giao hàng (account) hoặc chờ nâng cấp (upgrade)."""
    # Ack ngay để Telegram tắt spinner (giao hàng/gửi file có thể chậm hơn 15s -> tránh treo nút).
    await callback.answer("Đang xử lý...")
    order_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        order = await repo.get_order(session, order_id)
        if order is None:
            await callback.answer("Không tìm thấy đơn.", show_alert=True)
            return
        result = await order_service.approve_order(session, order, callback.from_user.id)

    if not result.ok:
        await callback.answer("Đơn không còn ở trạng thái chờ (đã xử lý/hết hạn).", show_alert=True)
        await _strip_review_buttons(callback, "⚠️ Đơn đã được xử lý trước đó.")
        return

    if result.delivered:
        await delivery.deliver(callback.bot, order, result.payloads)
        logger.info("Admin %s duyệt & giao đơn %s", callback.from_user.id, order.code)
        await _strip_review_buttons(callback, f"✅ Đã duyệt & giao hàng (bởi {callback.from_user.id}).")
    elif result.awaiting_upgrade:
        await delivery.notify_upgrade_pending(callback.bot, order)
        logger.info("Admin %s duyệt đơn nâng cấp %s", callback.from_user.id, order.code)
        await _strip_review_buttons(callback, f"✅ Đã duyệt, chờ nâng cấp (bởi {callback.from_user.id}).")


@router.callback_query(lambda c: c.data and c.data.startswith("adm_no:"))
async def cb_admin_reject(callback: CallbackQuery) -> None:
    """Admin Từ chối đơn -> huỷ + trả kho + báo khách."""
    # Ack ngay để Telegram tắt spinner trước khi báo khách (gửi tin có thể chậm).
    await callback.answer("Đang xử lý...")
    order_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        order = await repo.get_order(session, order_id)
        if order is None:
            await callback.answer("Không tìm thấy đơn.", show_alert=True)
            return
        ok = await order_service.reject_order(session, order)

    if not ok:
        await callback.answer("Đơn không còn ở trạng thái chờ (đã xử lý/hết hạn).", show_alert=True)
        await _strip_review_buttons(callback, "⚠️ Đơn đã được xử lý trước đó.")
        return

    try:
        await callback.bot.send_message(
            order.buyer_tg_id,
            f"❌ Đơn <code>{order.code}</code> đã bị từ chối (không xác nhận được thanh toán).\n"
            "Nếu bạn đã chuyển khoản, vui lòng liên hệ hỗ trợ để được kiểm tra lại.",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Báo khách từ chối đơn %s thất bại: %s", order.code, exc)

    logger.info("Admin %s từ chối đơn %s", callback.from_user.id, order.code)
    await _strip_review_buttons(callback, f"❌ Đã từ chối (bởi {callback.from_user.id}).")
