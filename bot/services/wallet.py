from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import models, repo
from bot.db.models import User, WalletTx
from bot.services import payment

# Giới hạn số tiền nạp 1 lần để tránh nhập nhầm / lạm dụng.
MIN_TOPUP = 10_000
MAX_TOPUP = 50_000_000


@dataclass
class TopUpRequest:
    tx: WalletTx
    qr_url: str
    code: str


async def _unique_topup_code(session: AsyncSession, max_tries: int = 12) -> str:
    """Sinh mã nạp tiền ngẫu nhiên chưa tồn tại trong sổ ví."""
    for _ in range(max_tries):
        code = payment.generate_order_code()
        if await repo.get_wallet_tx_by_code(session, code) is None:
            return code
    return payment.generate_order_code(payment.ORDER_CODE_LENGTH + 4)


class InvalidAmount(Exception):
    pass


async def request_topup(
    session: AsyncSession, *, tg_id: int, username: str | None, amount: int
) -> TopUpRequest:
    """Tạo yêu cầu nạp tiền (pending) + QR. Chưa cộng số dư cho tới khi admin duyệt."""
    if amount < MIN_TOPUP or amount > MAX_TOPUP:
        raise InvalidAmount()
    user = await repo.upsert_user(session, tg_id, username)
    code = await _unique_topup_code(session)
    tx = await repo.create_pending_topup(session, user, amount, code)
    await session.commit()
    qr_url = payment.build_qr_url(amount, code)
    return TopUpRequest(tx=tx, qr_url=qr_url, code=code)


async def confirm_topup(session: AsyncSession, code: str, admin_id: int) -> WalletTx | None:
    """Admin duyệt nạp tiền -> cộng số dư. Trả WalletTx đã confirmed, hoặc None nếu không hợp lệ."""
    tx = await repo.confirm_topup(session, code, admin_id)
    if tx is not None:
        await session.commit()
    return tx


async def reject_topup(session: AsyncSession, code: str) -> WalletTx | None:
    tx = await repo.reject_topup(session, code)
    if tx is not None:
        await session.commit()
    return tx


async def admin_adjust(
    session: AsyncSession, *, tg_id: int, amount: int, note: str = ""
) -> tuple[bool, User | None]:
    """Admin cộng (amount>0) / trừ (amount<0) tiền ví. Trả (ok, user)."""
    ok, user = await repo.adjust_balance(session, tg_id, amount, note=note)
    if ok:
        await session.commit()
    return ok, user
