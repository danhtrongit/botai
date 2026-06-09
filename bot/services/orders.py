from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.db import models, repo
from bot.db.models import Order
from bot.services import payment

# Serialize cấp phát kho để 2 đơn không giành cùng StockItem (SQLite ghi tuần tự, lock này
# bảo đảm an toàn ở tầng ứng dụng cho cả engine không hỗ trợ SELECT ... FOR UPDATE thực sự).
_alloc_lock = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _unique_order_code(session: AsyncSession, max_tries: int = 12) -> str:
    """Sinh mã đơn ngẫu nhiên chưa tồn tại trong DB (thử lại nếu trùng)."""
    for _ in range(max_tries):
        code = payment.generate_order_code()
        if await repo.get_order_by_code(session, code) is None:
            return code
    # Cực hiếm khi tới đây; nới dài thêm để chắc chắn không trùng.
    return payment.generate_order_code(payment.ORDER_CODE_LENGTH + 4)


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

        # Tạo đơn trước để lấy id, sau đó gán mã ngẫu nhiên duy nhất rồi reserve kho.
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
        order.code = await _unique_order_code(session)

        if not is_upgrade:
            reserved = await repo.reserve_items(session, product_id, quantity, order.id)
            if len(reserved) < quantity:
                # Có người khác vừa lấy mất (hiếm vì đã khóa) -> rollback toàn bộ.
                await session.rollback()
                raise OutOfStock(await repo.count_available(session, product_id))

        await session.commit()

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
class ApprovalResult:
    ok: bool
    delivered: bool = False
    payloads: list[str] = None  # type: ignore[assignment]
    awaiting_upgrade: bool = False
    reason: str = ""

    def __post_init__(self):
        if self.payloads is None:
            self.payloads = []


async def approve_order(session: AsyncSession, order: Order, admin_id: int) -> ApprovalResult:
    """Admin duyệt đơn pending bằng tay -> giao hàng.

    SP `account`: đánh dấu kho đã bán -> delivered (trả payloads để gửi file).
    SP `upgrade`: chuyển awaiting_upgrade để admin nâng cấp chính chủ theo email khách.
    Idempotent: nếu đơn không còn pending (đã duyệt / hết hạn) thì trả ok=False.
    """
    if order.status != models.PENDING:
        return ApprovalResult(ok=False, reason=f"status_{order.status}")

    order.payment_tx_id = f"manual:{admin_id}"
    order.paid_at = _now()

    product = await repo.get_product(session, order.product_id)
    if product is not None and product.kind == models.KIND_UPGRADE:
        # Không có kho để giao -> chờ admin nâng cấp chính chủ theo email khách.
        order.status = models.AWAITING_UPGRADE
        await session.commit()
        return ApprovalResult(ok=True, awaiting_upgrade=True)

    items = await repo.mark_order_items_sold(session, order.id)
    payloads = [item.payload for item in items]
    order.status = models.DELIVERED
    await session.commit()
    return ApprovalResult(ok=True, delivered=True, payloads=payloads)


async def reject_order(session: AsyncSession, order: Order) -> bool:
    """Admin từ chối đơn pending -> huỷ (expired) + trả kho. Trả True nếu đã xử lý."""
    if order.status != models.PENDING:
        return False
    order.status = models.EXPIRED
    await repo.release_order_items(session, order.id)
    await session.commit()
    return True


async def pay_with_wallet(session: AsyncSession, order: Order, user) -> ApprovalResult:
    """Thanh toán đơn pending bằng số dư ví -> giao ngay, không cần admin duyệt.

    Trừ ví (atomic, trong _alloc_lock để khỏi đua với luồng khác), rồi giao hàng như approve.
    Trả ok=False kèm reason nếu đơn không còn pending hoặc không đủ số dư.
    """
    async with _alloc_lock:
        if order.status != models.PENDING:
            return ApprovalResult(ok=False, reason=f"status_{order.status}")
        if user is None or user.balance < order.total_amount:
            return ApprovalResult(ok=False, reason="insufficient")

        charged = await repo.charge_wallet(
            session, user, order.total_amount,
            note=f"Mua đơn {order.code}", ref_code=order.code,
        )
        if not charged:
            return ApprovalResult(ok=False, reason="insufficient")

        order.payment_tx_id = f"wallet:{user.tg_id}"
        order.paid_at = _now()

        product = await repo.get_product(session, order.product_id)
        if product is not None and product.kind == models.KIND_UPGRADE:
            order.status = models.AWAITING_UPGRADE
            await session.commit()
            return ApprovalResult(ok=True, awaiting_upgrade=True)

        items = await repo.mark_order_items_sold(session, order.id)
        payloads = [item.payload for item in items]
        order.status = models.DELIVERED
        await session.commit()
        return ApprovalResult(ok=True, delivered=True, payloads=payloads)


async def expire_orders(session: AsyncSession) -> int:
    """Đổi đơn pending quá hạn -> expired và trả kho. Trả số đơn đã xử lý."""
    expired = await repo.list_expired_pending(session, _now())
    for order in expired:
        order.status = models.EXPIRED
        await repo.release_order_items(session, order.id)
    if expired:
        await session.commit()
    return len(expired)
