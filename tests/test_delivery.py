from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.services import delivery


async def test_deliver_sends_txt_file_with_special_chars():
    bot = AsyncMock()
    order = SimpleNamespace(code="BOT000016", buyer_tg_id=7567124001)
    # Payload chứa ký tự kiểu thẻ HTML từng gây lỗi "Unsupported start tag".
    payloads = ["user1|pass<c4fote2s5>", "user2|p&w<b>x"]

    ok = await delivery.deliver(bot, order, payloads)

    assert ok is True
    bot.send_document.assert_awaited_once()
    doc = bot.send_document.await_args.kwargs["document"]
    assert doc.filename == "BOT000016.txt"
    # Nội dung tài khoản nằm nguyên trong file (không bị parse HTML)
    content = bytes(doc.data).decode("utf-8")
    assert "user1|pass<c4fote2s5>" in content
    assert "user2|p&w<b>x" in content
