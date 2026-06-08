from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import get_settings
from bot.middlewares import AdminOnlyMiddleware
from bot.services import webauth

router = Router(name="admin")
router.message.middleware(AdminOnlyMiddleware())


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
