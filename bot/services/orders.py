from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.db import models, repo
from bot.db.models import Order
from bot.services import payment, poll_signal

# Serialize cấp phát kho để 2 đơn không giành cùng StockItem (SQLite ghi tuần tự, lock này
# bảo đảm an toàn ở tầng ứng dụng cho cả engine không hỗ trợ SELECT ... FOR UPDATE thực sự).
_alloc_lock = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OutOfStock(Exception):
    def __init__(self, available: int):
        self.available = available
        super().__init__(f"Out of stock, available={available}")


class ProductUnavailable(Exception):
    pass


@dataclass
class CreatedOrder:
    order: Order
    qr_url: str


async def create_order(
    session: AsyncSession,
    *,
    buyer_tg_id: int,
    buyer_username: str | None,
    product_id: int,
    quantity: int,
    buyer_email: str | None = None,
) -> CreatedOrder:
    """Tạo đơn pending.

    SP `account`: reserve kho theo `quantity`. SP `upgrade`: không động kho, cố định 1 đơn vị,
    lưu `buyer_email` để admin nâng cấp thủ công.
    """
    settings = get_settings()
    async with _alloc_lock:
        product = await repo.get_product(session, product_id)
        if not product or not product.is_active:
            raise ProductUnavailable()

        is_upgrade = product.kind == models.KIND_UPGRADE
        if is_upgrade:
            quantity = 1  # đơn nâng cấp luôn 1 email/đơn
        else:
            available = await repo.count_available(session, product_id)
            if available < quantity:
                raise OutOfStock(available)

        total_amount = product.price * quantity
        expires_at = _now() + timedelta(minutes=settings.order_expiry_minutes)

        # Tạo đơn trước để lấy id -> sinh mã đơn ổn định, rồi reserve kho theo order_id.
        order = await repo.create_order(
            session,
            code="PENDING",  # tạm; cập nhật ngay sau khi có id
            buyer_tg_id=buyer_tg_id,
            buyer_username=buyer_username,
            buyer_email=buyer_email,
            product_id=product_id,
            quantity=quantity,
            total_amount=total_amount,
            expires_at=expires_at,
        )
        order.code = payment.build_order_code(order.id)

        if not is_upgrade:
            reserved = await repo.reserve_items(session, product_id, quantity, order.id)
            if len(reserved) < quantity:
                # Có người khác vừa lấy mất (hiếm vì đã khóa) -> rollback toàn bộ.
                await session.rollback()
                raise OutOfStock(await repo.count_available(session, product_id))

        await session.commit()

    # Có đơn pending mới -> đánh thức bộ quét MBBank để bắt thanh toán.
    poll_signal.signal_new_order()

    qr_url = payment.build_qr_url(total_amount, order.code)
    return CreatedOrder(order=order, qr_url=qr_url)


async def cancel_order(session: AsyncSession, order: Order) -> bool:
    """Khách chủ động hủy đơn pending -> trả kho."""
    if order.status != models.PENDING:
        return False
    order.status = models.EXPIRED
    await repo.release_order_items(session, order.id)
    await session.commit()
    return True


@dataclass
class PaymentResult:
    delivered: bool
    payloads: list[str]
    reason: str = ""
    awaiting_upgrade: bool = False  # đơn nâng cấp đã trả tiền, chờ admin xử lý tay


async def confirm_payment(
    session: AsyncSession, order: Order, payment_tx_id: str, transfer_amount: int
) -> PaymentResult:
    """Đối soát thanh toán cho 1 đơn pending. Idempotency do webhook đã kiểm tra payment_tx_id.

    SP `account`: cấp phát kho -> delivered. SP `upgrade`: chuyển awaiting_upgrade để admin xử lý.
    """
    if order.status in (models.PAID, models.DELIVERED, models.AWAITING_UPGRADE):
        return PaymentResult(delivered=False, payloads=[], reason="already_processed")
    if order.status != models.PENDING:
        return PaymentResult(delivered=False, payloads=[], reason=f"status_{order.status}")
    if transfer_amount < order.total_amount:
        return PaymentResult(delivered=False, payloads=[], reason="underpaid")

    order.status = models.PAID
    order.payment_tx_id = payment_tx_id
    order.paid_at = _now()

    product = await repo.get_product(session, order.product_id)
    if product is not None and product.kind == models.KIND_UPGRADE:
        # Không có kho để giao -> chờ admin nâng cấp chính chủ theo email khách.
        order.status = models.AWAITING_UPGRADE
        await session.commit()
        return PaymentResult(delivered=False, payloads=[], reason="upgrade", awaiting_upgrade=True)

    items = await repo.mark_order_items_sold(session, order.id)
    payloads = [item.payload for item in items]
    order.status = models.DELIVERED
    await session.commit()
    return PaymentResult(delivered=True, payloads=payloads)


async def expire_orders(session: AsyncSession) -> int:
    """Đổi đơn pending quá hạn -> expired và trả kho. Trả số đơn đã xử lý."""
    expired = await repo.list_expired_pending(session, _now())
    for order in expired:
        order.status = models.EXPIRED
        await repo.release_order_items(session, order.id)
    if expired:
        await session.commit()
    return len(expired)
