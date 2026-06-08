from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from bot.config import get_settings


class AdminOnlyMiddleware(BaseMiddleware):
    """Chặn user không phải admin sử dụng các handler đã gắn middleware này."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        settings = get_settings()
        user = data.get("event_from_user")
        if user is None or not settings.is_admin(user.id):
            if isinstance(event, Message):
                await event.answer("⛔ Bạn không có quyền dùng lệnh này.")
            return None
        return await handler(event, data)
