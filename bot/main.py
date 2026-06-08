from __future__ import annotations

import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonCommands

from bot.config import get_settings
from bot.db.database import async_session, init_db
from bot.handlers import admin, user
from bot.services import mbbank_poll
from bot.services import orders as order_service
from webhook.server import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def expire_loop(interval_seconds: int = 60) -> None:
    """Định kỳ huỷ đơn pending quá hạn và trả kho."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with async_session() as session:
                n = await order_service.expire_orders(session)
            if n:
                logger.info("Đã hết hạn %s đơn", n)
        except Exception:  # noqa: BLE001
            logger.exception("Lỗi khi xử lý đơn hết hạn")


async def main() -> None:
    settings = get_settings()
    await init_db()

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(admin.router)
    dp.include_router(user.router)

    # FastAPI server (trang chủ + admin) dùng chung instance bot để giao hàng.
    app = create_app(bot)
    config = uvicorn.Config(
        app, host=settings.webhook_host, port=settings.webhook_port, log_level="info"
    )
    server = uvicorn.Server(config)

    logger.info("Khởi động bot (polling) + web server tại %s:%s + quét MBBank mỗi %ss",
                settings.webhook_host, settings.webhook_port, settings.mb_poll_interval)

    await bot.delete_webhook(drop_pending_updates=True)

    # Đăng ký menu lệnh "/" + nút Menu của Telegram để user biết bấm gì ngay.
    await bot.set_my_commands([
        BotCommand(command="start", description="Bắt đầu / về menu chính"),
        BotCommand(command="mua", description="🛒 Mua hàng"),
        BotCommand(command="donhang", description="📦 Đơn của tôi"),
        BotCommand(command="trogiup", description="ℹ️ Trợ giúp"),
    ])
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    await asyncio.gather(
        dp.start_polling(bot),
        server.serve(),
        expire_loop(),
        mbbank_poll.poll_loop(bot, settings.mb_poll_interval),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Đã dừng.")
