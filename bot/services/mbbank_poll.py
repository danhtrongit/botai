from __future__ import annotations

import asyncio
import datetime
import logging

from aiogram import Bot

from bot.db import repo
from bot.db.database import async_session
from bot.services import delivery, mb_store, payment, poll_signal
from bot.services import orders as order_service

logger = logging.getLogger(__name__)

# Giữ 1 client MBBank để tái dùng phiên trong khi còn đơn chờ. Bỏ phiên khi hết đơn.
_client: dict = {"mb": None, "user": None, "acct": None}


def _reset_client() -> None:
    """Bỏ phiên đăng nhập MBBank (gọi khi không còn đơn chờ) -> lần sau login mới."""
    _client["mb"] = None
    _client["user"] = None
    _client["acct"] = None


def _to_int(amount) -> int:
    try:
        return int(str(amount or "0").replace(",", "").replace(".", "").strip() or "0")
    except (ValueError, AttributeError):
        return 0


def _fetch_transactions_sync(username: str, password: str, account_no: str, days: int = 1) -> list[dict]:
    """Đăng nhập MBBank (lazy import) và lấy lịch sử giao dịch -> list dict. Chạy trong thread."""
    import mbbank  # noqa: PLC0415 — import trễ để môi trường không có mbbank vẫn chạy phần khác

    if _client["mb"] is None or _client["user"] != username:
        _client["mb"] = mbbank.MBBank(username=username, password=password)
        _client["user"] = username
        _client["acct"] = None

    mb = _client["mb"]
    try:
        acct = account_no or _client["acct"]
        if not acct:
            balance = mb.getBalance()
            acct = balance.acct_list[0].acctNo
            _client["acct"] = acct

        to_date = datetime.datetime.now()
        from_date = to_date - datetime.timedelta(days=days)
        history = mb.getTransactionAccountHistory(accountNo=acct, from_date=from_date, to_date=to_date)
    except Exception:
        # Reset để lần sau đăng nhập lại từ đầu.
        _client["mb"] = None
        _client["acct"] = None
        raise

    result = []
    for t in getattr(history, "transactionHistoryList", []) or []:
        result.append(
            {
                "refNo": getattr(t, "refNo", None),
                "creditAmount": getattr(t, "creditAmount", "0"),
                "debitAmount": getattr(t, "debitAmount", "0"),
                "description": getattr(t, "description", "") or "",
                "addDescription": getattr(t, "addDescription", "") or "",
            }
        )
    return result


async def process_transactions(bot: Bot, txns: list[dict]) -> int:
    """Đối soát danh sách giao dịch tiền-vào với đơn pending. Trả số đơn đã giao."""
    delivered_count = 0
    for tx in txns:
        credit = _to_int(tx.get("creditAmount"))
        if credit <= 0:
            continue
        ref = tx.get("refNo")
        if not ref:
            continue

        async with async_session() as session:
            # Idempotency: refNo đã xử lý -> bỏ qua.
            if await repo.get_order_by_payment_tx(session, ref) is not None:
                continue

            # Lấy danh sách mã đơn đang chờ rồi so khớp (chịu được nội dung CK bị tách ký tự).
            pending_codes = await repo.list_pending_order_codes(session)
            code = payment.match_order_code(
                pending_codes, tx.get("description"), tx.get("addDescription")
            )
            if not code:
                continue

            order = await repo.get_order_by_code(session, code)
            if order is None:
                continue

            result = await order_service.confirm_payment(
                session, order, payment_tx_id=ref, transfer_amount=credit
            )

        if result.delivered:
            await delivery.deliver(bot, order, result.payloads)
            delivered_count += 1
            logger.info("Đã giao đơn %s (refNo=%s)", order.code, ref)
        elif result.awaiting_upgrade:
            await delivery.notify_upgrade_pending(bot, order)
            delivered_count += 1
            logger.info("Đơn nâng cấp %s đã thanh toán, chờ admin (refNo=%s)", order.code, ref)
        elif result.reason == "underpaid":
            logger.info("Đơn %s chuyển thiếu tiền (refNo=%s)", order.code, ref)

    return delivered_count


async def poll_loop(bot: Bot, interval: int) -> None:
    """Chỉ đăng nhập & quét MBBank KHI có đơn chờ thanh toán.

    Không có đơn pending: bỏ phiên đăng nhập và ngủ tới khi `create_order` báo có đơn mới
    (tránh giữ phiên / login liên tục gây khoá tài khoản). Có đơn: quét theo `interval` cho tới
    khi hết đơn chờ.
    """
    logged_missing = False
    while True:
        try:
            async with async_session() as session:
                creds = await mb_store.get_credentials(session)
                pending = await repo.count_pending_orders(session)

            if creds is None:
                if not logged_missing:
                    logger.info("Chưa cấu hình MBBank (vào /admin để nhập TK/MK) — tạm dừng quét.")
                    logged_missing = True
                _reset_client()
                await poll_signal.wait_for_order()
                continue
            logged_missing = False

            if pending == 0:
                # Hết đơn chờ -> bỏ phiên đăng nhập và ngủ hẳn tới khi có đơn mới.
                _reset_client()
                await poll_signal.wait_for_order()
                continue

            txns = await asyncio.to_thread(
                _fetch_transactions_sync, creds.username, creds.password, creds.account_no
            )
            n = await process_transactions(bot, txns)
            if n:
                logger.info("Quét MBBank: đã xử lý %s đơn", n)

            # Còn đơn chờ -> ngủ tới `interval`, hoặc thức sớm nếu có đơn mới, rồi quét tiếp.
            await poll_signal.wait_or_timeout(interval)
        except Exception:  # noqa: BLE001
            logger.exception("Lỗi khi quét MBBank")
            await asyncio.sleep(interval)
