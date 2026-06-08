from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import models
from bot.db.models import AppSetting, Order, Product, StockItem


# ---------- App settings (key-value) ----------

async def get_setting(session: AsyncSession, key: str) -> str | None:
    row = await session.get(AppSetting, key)
    return row.value if row else None


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(AppSetting, key)
    if row:
        row.value = value
    else:
        session.add(AppSetting(key=key, value=value))
    await session.flush()


# ---------- Products ----------

async def create_product(
    session: AsyncSession,
    name: str,
    price: int,
    description: str = "",
    kind: str = models.KIND_ACCOUNT,
) -> Product:
    product = Product(name=name, price=price, description=description, kind=kind)
    session.add(product)
    await session.flush()
    return product


async def get_product(session: AsyncSession, product_id: int) -> Product | None:
    return await session.get(Product, product_id)


async def count_orders_for_product(session: AsyncSession, product_id: int) -> int:
    stmt = select(func.count(Order.id)).where(Order.product_id == product_id)
    return int((await session.scalar(stmt)) or 0)


async def delete_product(session: AsyncSession, product_id: int) -> str:
    """Xoá sản phẩm. Chặn nếu đã có đơn (giữ lịch sử). Trả 'ok'|'has_orders'|'not_found'."""
    product = await session.get(Product, product_id)
    if not product:
        return "not_found"
    if await count_orders_for_product(session, product_id) > 0:
        return "has_orders"
    await session.execute(delete(StockItem).where(StockItem.product_id == product_id))
    await session.delete(product)
    return "ok"


async def list_products(session: AsyncSession, only_active: bool = True) -> list[Product]:
    stmt = select(Product).order_by(Product.id)
    if only_active:
        stmt = stmt.where(Product.is_active.is_(True))
    return list((await session.scalars(stmt)).all())


async def set_product_active(session: AsyncSession, product_id: int, active: bool) -> bool:
    product = await session.get(Product, product_id)
    if not product:
        return False
    product.is_active = active
    return True


async def update_product(
    session: AsyncSession,
    product_id: int,
    *,
    name: str | None = None,
    price: int | None = None,
    description: str | None = None,
    kind: str | None = None,
) -> bool:
    product = await session.get(Product, product_id)
    if not product:
        return False
    if name is not None:
        product.name = name
    if price is not None:
        product.price = price
    if description is not None:
        product.description = description
    if kind is not None:
        product.kind = kind
    return True


# ---------- Stock ----------

async def add_stock(session: AsyncSession, product_id: int, payloads: list[str], cost: int = 0) -> int:
    """Nạp lô tài khoản; cả lô dùng chung một giá vốn `cost`."""
    items = [StockItem(product_id=product_id, payload=p, cost=cost) for p in payloads]
    session.add_all(items)
    await session.flush()
    return len(items)


async def list_stock_items(session: AsyncSession, product_id: int, limit: int = 500) -> list[StockItem]:
    stmt = (
        select(StockItem)
        .where(StockItem.product_id == product_id)
        .order_by(StockItem.id.desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def get_stock_item(session: AsyncSession, item_id: int) -> StockItem | None:
    return await session.get(StockItem, item_id)


async def update_stock_item(
    session: AsyncSession,
    item_id: int,
    *,
    payload: str | None = None,
    status: str | None = None,
    cost: int | None = None,
) -> bool:
    item = await session.get(StockItem, item_id)
    if not item:
        return False
    if payload is not None:
        item.payload = payload
    if cost is not None:
        item.cost = cost
    if status is not None:
        item.status = status
        if status == models.AVAILABLE:
            item.order_id = None  # trả về kho -> bỏ gắn đơn
    return True


async def delete_stock_item(session: AsyncSession, item_id: int) -> int | None:
    """Xoá 1 tài khoản trong kho. Trả product_id nếu xoá được, None nếu không có."""
    item = await session.get(StockItem, item_id)
    if not item:
        return None
    product_id = item.product_id
    await session.delete(item)
    return product_id


async def count_available(session: AsyncSession, product_id: int) -> int:
    stmt = select(func.count(StockItem.id)).where(
        StockItem.product_id == product_id, StockItem.status == models.AVAILABLE
    )
    return int((await session.scalar(stmt)) or 0)


async def stock_summary(session: AsyncSession, product_id: int) -> dict[str, int]:
    stmt = (
        select(StockItem.status, func.count(StockItem.id))
        .where(StockItem.product_id == product_id)
        .group_by(StockItem.status)
    )
    rows = (await session.execute(stmt)).all()
    summary = {models.AVAILABLE: 0, models.RESERVED: 0, models.SOLD: 0}
    for status, count in rows:
        summary[status] = int(count)
    return summary


async def reserve_items(session: AsyncSession, product_id: int, quantity: int, order_id: int) -> list[StockItem]:
    """Lấy `quantity` item available và đổi sang reserved gắn với order. Trả [] nếu không đủ."""
    stmt = (
        select(StockItem)
        .where(StockItem.product_id == product_id, StockItem.status == models.AVAILABLE)
        .order_by(StockItem.id)
        .limit(quantity)
        .with_for_update()
    )
    items = list((await session.scalars(stmt)).all())
    if len(items) < quantity:
        return []
    for item in items:
        item.status = models.RESERVED
        item.order_id = order_id
    await session.flush()
    return items


async def release_order_items(session: AsyncSession, order_id: int) -> int:
    stmt = (
        update(StockItem)
        .where(StockItem.order_id == order_id, StockItem.status == models.RESERVED)
        .values(status=models.AVAILABLE, order_id=None)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def mark_order_items_sold(session: AsyncSession, order_id: int) -> list[StockItem]:
    stmt = select(StockItem).where(StockItem.order_id == order_id).order_by(StockItem.id)
    items = list((await session.scalars(stmt)).all())
    for item in items:
        item.status = models.SOLD
    await session.flush()
    return items


# ---------- Orders ----------

async def create_order(
    session: AsyncSession,
    *,
    code: str,
    buyer_tg_id: int,
    buyer_username: str | None,
    product_id: int,
    quantity: int,
    total_amount: int,
    expires_at: datetime,
    buyer_email: str | None = None,
) -> Order:
    order = Order(
        code=code,
        buyer_tg_id=buyer_tg_id,
        buyer_username=buyer_username,
        buyer_email=buyer_email,
        product_id=product_id,
        quantity=quantity,
        total_amount=total_amount,
        expires_at=expires_at,
    )
    session.add(order)
    await session.flush()
    return order


async def get_order(session: AsyncSession, order_id: int) -> Order | None:
    return await session.get(Order, order_id)


async def get_order_by_code(session: AsyncSession, code: str) -> Order | None:
    return await session.scalar(select(Order).where(Order.code == code))


async def get_order_by_payment_tx(session: AsyncSession, payment_tx_id: str) -> Order | None:
    return await session.scalar(select(Order).where(Order.payment_tx_id == payment_tx_id))


async def list_orders_by_buyer(session: AsyncSession, buyer_tg_id: int, limit: int = 10) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.buyer_tg_id == buyer_tg_id)
        .order_by(Order.id.desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def list_recent_orders(session: AsyncSession, limit: int = 20) -> list[Order]:
    stmt = select(Order).order_by(Order.id.desc()).limit(limit)
    return list((await session.scalars(stmt)).all())


async def list_orders(session: AsyncSession, limit: int = 100, status: str | None = None) -> list[Order]:
    stmt = select(Order).order_by(Order.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(Order.status == status)
    return list((await session.scalars(stmt)).all())


async def get_order_items(session: AsyncSession, order_id: int) -> list[StockItem]:
    stmt = select(StockItem).where(StockItem.order_id == order_id).order_by(StockItem.id)
    return list((await session.scalars(stmt)).all())


async def list_sold_items(session: AsyncSession, limit: int = 200) -> list:
    """Trả các Row(StockItem, Order, Product) của tài khoản đã bán, mới nhất trước."""
    stmt = (
        select(StockItem, Order, Product)
        .join(Order, StockItem.order_id == Order.id)
        .join(Product, StockItem.product_id == Product.id)
        .where(StockItem.status == models.SOLD)
        .order_by(StockItem.id.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).all())


async def count_pending_orders(session: AsyncSession) -> int:
    """Số đơn đang chờ thanh toán (dùng để quyết định có cần quét MBBank không)."""
    stmt = select(func.count(Order.id)).where(Order.status == models.PENDING)
    return int((await session.scalar(stmt)) or 0)


async def complete_upgrade(session: AsyncSession, order: Order, cost: int | None = None) -> bool:
    """Admin xác nhận đã nâng cấp xong đơn awaiting_upgrade -> delivered (kèm giá vốn nếu có)."""
    if order.status != models.AWAITING_UPGRADE:
        return False
    if cost is not None:
        order.cost = max(0, cost)
    order.status = models.DELIVERED
    await session.flush()
    return True


async def set_order_cost(session: AsyncSession, order: Order, cost: int) -> None:
    """Cập nhật giá vốn của 1 đơn (dùng cho đơn nâng cấp đã giao)."""
    order.cost = max(0, cost)
    await session.flush()


async def list_expired_pending(session: AsyncSession, now: datetime) -> list[Order]:
    stmt = select(Order).where(
        Order.status == models.PENDING,
        Order.expires_at.is_not(None),
        Order.expires_at < now,
    )
    return list((await session.scalars(stmt)).all())


async def revenue_summary(session: AsyncSession) -> tuple[int, int]:
    """Trả (tổng doanh thu, số đơn delivered)."""
    stmt = select(func.coalesce(func.sum(Order.total_amount), 0), func.count(Order.id)).where(
        Order.status == models.DELIVERED
    )
    total, count = (await session.execute(stmt)).one()
    return int(total), int(count)


async def profit_summary(session: AsyncSession) -> tuple[int, int, int, int]:
    """Trả (doanh thu, giá vốn, lợi nhuận, số đơn đã giao).

    Doanh thu = tổng tiền đơn delivered. Giá vốn = tổng cost của tài khoản đã bán.
    """
    revenue, count = await revenue_summary(session)
    # Giá vốn = giá vốn TK đã bán (đơn thường) + giá vốn đơn nâng cấp đã giao.
    stock_cost = await session.scalar(
        select(func.coalesce(func.sum(StockItem.cost), 0)).where(StockItem.status == models.SOLD)
    )
    order_cost = await session.scalar(
        select(func.coalesce(func.sum(Order.cost), 0)).where(Order.status == models.DELIVERED)
    )
    cost = int(stock_cost or 0) + int(order_cost or 0)
    return revenue, cost, revenue - cost, count
