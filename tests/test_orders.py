from __future__ import annotations

import pytest

from bot.db import models, repo
from bot.services import orders as order_service


async def _seed_product(session, price=10000, stock=5):
    product = await repo.create_product(session, name="Netflix", price=price, description="1 thang")
    await session.flush()
    await repo.add_stock(session, product.id, [f"user{i}|pass{i}" for i in range(stock)])
    await session.commit()
    return product


async def test_create_order_reserves_stock(session):
    product = await _seed_product(session, price=10000, stock=5)

    created = await order_service.create_order(
        session, buyer_tg_id=111, buyer_username="alice", product_id=product.id, quantity=2
    )

    from bot.services import payment

    assert len(created.order.code) == payment.ORDER_CODE_LENGTH
    assert all(c in payment.ORDER_CODE_ALPHABET for c in created.order.code)
    assert created.order.total_amount == 20000
    assert created.order.status == models.PENDING
    summary = await repo.stock_summary(session, product.id)
    assert summary[models.AVAILABLE] == 3
    assert summary[models.RESERVED] == 2


async def test_create_order_out_of_stock(session):
    product = await _seed_product(session, stock=1)
    with pytest.raises(order_service.OutOfStock):
        await order_service.create_order(
            session, buyer_tg_id=1, buyer_username=None, product_id=product.id, quantity=2
        )


async def test_approve_order_delivers(session):
    product = await _seed_product(session, price=10000, stock=5)
    created = await order_service.create_order(
        session, buyer_tg_id=111, buyer_username="alice", product_id=product.id, quantity=2
    )

    result = await order_service.approve_order(session, created.order, admin_id=999)

    assert result.ok is True
    assert result.delivered is True
    assert len(result.payloads) == 2
    assert created.order.status == models.DELIVERED
    assert created.order.payment_tx_id == "manual:999"
    summary = await repo.stock_summary(session, product.id)
    assert summary[models.SOLD] == 2
    assert summary[models.AVAILABLE] == 3


async def test_reject_order_releases_stock(session):
    product = await _seed_product(session, price=10000, stock=5)
    created = await order_service.create_order(
        session, buyer_tg_id=1, buyer_username=None, product_id=product.id, quantity=2
    )

    ok = await order_service.reject_order(session, created.order)

    assert ok is True
    assert created.order.status == models.EXPIRED
    summary = await repo.stock_summary(session, product.id)
    assert summary[models.AVAILABLE] == 5
    assert summary[models.RESERVED] == 0


async def test_approve_order_idempotent_on_already_delivered(session):
    product = await _seed_product(session, price=10000, stock=5)
    created = await order_service.create_order(
        session, buyer_tg_id=1, buyer_username=None, product_id=product.id, quantity=1
    )
    await order_service.approve_order(session, created.order, admin_id=1)

    again = await order_service.approve_order(session, created.order, admin_id=1)
    assert again.ok is False
    summary = await repo.stock_summary(session, product.id)
    assert summary[models.SOLD] == 1


async def test_reject_after_approve_noop(session):
    product = await _seed_product(session, price=10000, stock=5)
    created = await order_service.create_order(
        session, buyer_tg_id=1, buyer_username=None, product_id=product.id, quantity=1
    )
    await order_service.approve_order(session, created.order, admin_id=1)
    # Đã giao rồi thì từ chối không còn tác dụng.
    assert await order_service.reject_order(session, created.order) is False
    assert created.order.status == models.DELIVERED


async def test_profit_summary(session):
    product = await repo.create_product(session, name="X", price=10000)
    await session.flush()
    await repo.add_stock(session, product.id, ["a|1", "b|2"], cost=4000)  # cả lô 4000/TK
    await session.commit()
    created = await order_service.create_order(
        session, buyer_tg_id=1, buyer_username=None, product_id=product.id, quantity=2
    )
    await order_service.approve_order(session, created.order, admin_id=1)

    revenue, cost, profit, count = await repo.profit_summary(session)
    assert revenue == 20000
    assert cost == 8000          # 2 TK đã bán x 4000
    assert profit == 12000
    assert count == 1


async def _seed_upgrade(session, price=50000):
    product = await repo.create_product(
        session, name="Nâng cấp Spotify", price=price, kind=models.KIND_UPGRADE
    )
    await session.commit()
    return product


async def test_create_upgrade_order_collects_email_no_stock(session):
    product = await _seed_upgrade(session, price=50000)
    created = await order_service.create_order(
        session, buyer_tg_id=1, buyer_username=None, product_id=product.id,
        quantity=3, buyer_email="me@mail.com",
    )
    assert created.order.quantity == 1            # đơn nâng cấp ép về 1
    assert created.order.total_amount == 50000
    assert created.order.buyer_email == "me@mail.com"
    assert created.order.status == models.PENDING
    # không reserve / tạo stock item nào
    assert await repo.get_order_items(session, created.order.id) == []


async def test_approve_order_upgrade_awaiting(session):
    product = await _seed_upgrade(session, price=50000)
    created = await order_service.create_order(
        session, buyer_tg_id=1, buyer_username=None, product_id=product.id,
        quantity=1, buyer_email="me@mail.com",
    )
    result = await order_service.approve_order(session, created.order, admin_id=7)
    assert result.ok is True
    assert result.delivered is False
    assert result.awaiting_upgrade is True
    assert created.order.status == models.AWAITING_UPGRADE
    assert created.order.payment_tx_id == "manual:7"


async def test_approve_order_upgrade_idempotent(session):
    product = await _seed_upgrade(session)
    created = await order_service.create_order(
        session, buyer_tg_id=1, buyer_username=None, product_id=product.id,
        quantity=1, buyer_email="me@mail.com",
    )
    await order_service.approve_order(session, created.order, admin_id=1)
    again = await order_service.approve_order(session, created.order, admin_id=1)
    assert again.ok is False
    assert again.awaiting_upgrade is False


async def test_complete_upgrade_with_cost(session):
    product = await _seed_upgrade(session, price=50000)
    created = await order_service.create_order(
        session, buyer_tg_id=1, buyer_username=None, product_id=product.id,
        quantity=1, buyer_email="x@y.com",
    )
    await order_service.approve_order(session, created.order, admin_id=1)
    ok = await repo.complete_upgrade(session, created.order, cost=12000)
    assert ok is True
    assert created.order.status == models.DELIVERED
    assert created.order.cost == 12000
    # gọi lại không hợp lệ
    assert await repo.complete_upgrade(session, created.order, cost=1) is False

    # giá vốn đơn nâng cấp vào báo cáo lợi nhuận
    revenue, cost, profit, count = await repo.profit_summary(session)
    assert revenue == 50000
    assert cost == 12000
    assert profit == 38000
    assert count == 1

    # sửa lại giá vốn sau khi đã giao
    await repo.set_order_cost(session, created.order, 20000)
    _, cost2, profit2, _ = await repo.profit_summary(session)
    assert cost2 == 20000
    assert profit2 == 30000


async def test_count_pending_orders(session):
    product = await _seed_product(session, price=10000, stock=5)
    assert await repo.count_pending_orders(session) == 0
    await order_service.create_order(
        session, buyer_tg_id=1, buyer_username=None, product_id=product.id, quantity=1
    )
    assert await repo.count_pending_orders(session) == 1


async def test_cancel_order_releases_stock(session):
    product = await _seed_product(session, stock=3)
    created = await order_service.create_order(
        session, buyer_tg_id=1, buyer_username=None, product_id=product.id, quantity=2
    )

    ok = await order_service.cancel_order(session, created.order)
    assert ok is True
    assert created.order.status == models.EXPIRED
    summary = await repo.stock_summary(session, product.id)
    assert summary[models.AVAILABLE] == 3
    assert summary[models.RESERVED] == 0
