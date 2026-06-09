from __future__ import annotations

import asyncio
import html
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from bot.db import models, repo
from bot.db.database import async_session
from bot.services import delivery, wallet, webauth

logger = logging.getLogger(__name__)

# Thư mục build của SPA admin (Vite). Deploy mới build -> có thể không tồn tại khi dev.
_DIST_DIR = Path(__file__).resolve().parent.parent / "admin" / "dist"
_INDEX_HTML = _DIST_DIR / "index.html"

_KIND_LABEL = {models.KIND_ACCOUNT: "Tài khoản", models.KIND_UPGRADE: "Nâng cấp chính chủ"}
_STOCK_STATUSES = (models.AVAILABLE, models.RESERVED, models.SOLD)


# ---------- Auth helpers ----------

def _current_admin(request: Request) -> int | None:
    token = request.cookies.get(webauth.COOKIE_NAME)
    if not token:
        return None
    return webauth.verify_token(token, webauth.COOKIE_MAX_AGE)


def require_admin(request: Request) -> int:
    """Dependency: trả admin_id hoặc 401 JSON nếu chưa đăng nhập."""
    admin_id = _current_admin(request)
    if admin_id is None:
        raise HTTPException(status_code=401, detail="Cần đăng nhập")
    return admin_id


# ---------- Serializers ----------

def _product_dict(p: models.Product, summary: dict[str, int] | None = None) -> dict:
    data = {
        "id": p.id,
        "name": p.name,
        "description": p.description or "",
        "price": p.price,
        "kind": p.kind,
        "kind_label": _KIND_LABEL.get(p.kind, p.kind),
        "is_active": p.is_active,
        "created_at": str(p.created_at) if p.created_at else None,
    }
    if summary is not None:
        data["stock"] = {
            "available": summary.get(models.AVAILABLE, 0),
            "reserved": summary.get(models.RESERVED, 0),
            "sold": summary.get(models.SOLD, 0),
        }
    return data


def _order_dict(o: models.Order, product_name: str | None = None) -> dict:
    return {
        "id": o.id,
        "code": o.code,
        "buyer_tg_id": o.buyer_tg_id,
        "buyer_username": o.buyer_username,
        "buyer_email": o.buyer_email,
        "product_id": o.product_id,
        "product_name": product_name,
        "quantity": o.quantity,
        "total_amount": o.total_amount,
        "cost": o.cost or 0,
        "status": o.status,
        "payment_tx_id": o.payment_tx_id,
        "created_at": str(o.created_at) if o.created_at else None,
        "paid_at": str(o.paid_at) if o.paid_at else None,
        "expires_at": str(o.expires_at) if o.expires_at else None,
    }


def _stock_dict(it: models.StockItem) -> dict:
    return {
        "id": it.id,
        "payload": it.payload,
        "cost": it.cost or 0,
        "status": it.status,
        "order_id": it.order_id,
    }


def _user_dict(u: models.User) -> dict:
    return {
        "tg_id": u.tg_id,
        "username": u.username,
        "balance": u.balance,
        "created_at": str(u.created_at) if u.created_at else None,
        "updated_at": str(u.updated_at) if u.updated_at else None,
    }


def _wallet_tx_dict(tx: models.WalletTx) -> dict:
    return {
        "id": tx.id,
        "amount": tx.amount,
        "type": tx.type,
        "status": tx.status,
        "note": tx.note or "",
        "ref_code": tx.ref_code,
        "balance_after": tx.balance_after,
        "created_at": str(tx.created_at) if tx.created_at else None,
    }


async def _safe_send(bot: Bot, chat_id: int, text: str) -> None:
    """Gửi tin Telegram, nuốt lỗi (user chặn bot...) để không vỡ tác vụ nền."""
    try:
        await bot.send_message(chat_id, text)
    except TelegramAPIError as exc:
        logger.info("Gửi thông báo cho user %s thất bại (bỏ qua): %s", chat_id, exc)


def create_admin_router(bot: Bot | None = None) -> APIRouter:
    router = APIRouter(prefix="/admin")

    # ---------- Auth (cookie) ----------

    @router.get("/auth")
    async def auth(token: str = ""):
        admin_id = webauth.verify_token(token, webauth.LOGIN_LINK_MAX_AGE)
        if admin_id is None:
            return HTMLResponse(
                "<h1>Liên kết không hợp lệ hoặc đã hết hạn</h1>"
                "<p>Mở bot Telegram và gửi <b>/login</b> để lấy liên kết mới.</p>",
                status_code=401,
            )
        resp = RedirectResponse(url="/admin/", status_code=303)
        resp.set_cookie(
            webauth.COOKIE_NAME, webauth.make_token(admin_id),
            max_age=webauth.COOKIE_MAX_AGE, httponly=True, samesite="lax",
        )
        return resp

    @router.get("/api/logout")
    async def logout():
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(webauth.COOKIE_NAME)
        return resp

    @router.get("/api/session")
    async def session_info(admin_id: int = Depends(require_admin)):
        return {"admin_id": admin_id, "authenticated": True}

    # ---------- Overview ----------

    @router.get("/api/overview")
    async def overview(admin_id: int = Depends(require_admin)):
        async with async_session() as session:
            revenue, cost, profit, count = await repo.profit_summary(session)
            orders = await repo.list_recent_orders(session, limit=10)
            products = {p.id: p.name for p in await repo.list_products(session, only_active=False)}

        return {
            "stats": {"revenue": revenue, "cost": cost, "profit": profit, "delivered": count},
            "recent_orders": [_order_dict(o, products.get(o.product_id)) for o in orders],
        }

    # ---------- Products ----------

    @router.get("/api/products")
    async def products_list(admin_id: int = Depends(require_admin)):
        async with async_session() as session:
            products = await repo.list_products(session, only_active=False)
            result = []
            for p in products:
                summary = await repo.stock_summary(session, p.id)
                result.append(_product_dict(p, summary))
        return {"products": result}

    @router.post("/api/products")
    async def create_product(payload: dict = Body(...), admin_id: int = Depends(require_admin)):
        name = (payload.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="Thiếu tên sản phẩm")
        price = int(payload.get("price") or 0)
        description = (payload.get("description") or "").strip()
        kind = payload.get("kind") if payload.get("kind") in _KIND_LABEL else models.KIND_ACCOUNT
        async with async_session() as session:
            p = await repo.create_product(session, name=name, price=price, description=description, kind=kind)
            await session.commit()
            return {"product": _product_dict(p)}

    @router.patch("/api/products/{product_id}")
    async def update_product(product_id: int, payload: dict = Body(...), admin_id: int = Depends(require_admin)):
        name = payload.get("name")
        price = payload.get("price")
        description = payload.get("description")
        kind = payload.get("kind")
        is_active = payload.get("is_active")
        if kind is not None and kind not in _KIND_LABEL:
            kind = models.KIND_ACCOUNT
        async with async_session() as session:
            ok = await repo.update_product(
                session, product_id,
                name=name.strip() if isinstance(name, str) else None,
                price=int(price) if price is not None else None,
                description=description.strip() if isinstance(description, str) else None,
                kind=kind,
            )
            if not ok:
                raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
            if is_active is not None:
                await repo.set_product_active(session, product_id, bool(is_active))
            await session.commit()
            p = await repo.get_product(session, product_id)
            summary = await repo.stock_summary(session, product_id)
            return {"product": _product_dict(p, summary)}

    @router.post("/api/products/{product_id}/toggle")
    async def toggle_product(product_id: int, admin_id: int = Depends(require_admin)):
        async with async_session() as session:
            product = await repo.get_product(session, product_id)
            if not product:
                raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
            product.is_active = not product.is_active
            await session.commit()
            return {"product": _product_dict(product)}

    @router.delete("/api/products/{product_id}")
    async def delete_product(product_id: int, admin_id: int = Depends(require_admin)):
        async with async_session() as session:
            result = await repo.delete_product(session, product_id)
            await session.commit()
        if result == "has_orders":
            raise HTTPException(status_code=409, detail="Sản phẩm đã có đơn hàng, hãy ẩn thay vì xoá")
        if result == "not_found":
            raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
        return {"ok": True}

    # ---------- Stock ----------

    @router.get("/api/products/{product_id}/stock")
    async def product_stock(product_id: int, admin_id: int = Depends(require_admin)):
        async with async_session() as session:
            product = await repo.get_product(session, product_id)
            if not product:
                raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
            items = await repo.list_stock_items(session, product_id)
            summary = await repo.stock_summary(session, product_id)
        return {
            "product": _product_dict(product, summary),
            "items": [_stock_dict(it) for it in items],
        }

    @router.post("/api/stock")
    async def add_stock(payload: dict = Body(...), admin_id: int = Depends(require_admin)):
        product_id = int(payload.get("product_id") or 0)
        cost = max(0, int(payload.get("cost") or 0))
        items_raw = payload.get("items") or ""
        lines = [line.strip() for line in items_raw.splitlines() if line.strip()]
        if not lines:
            raise HTTPException(status_code=422, detail="Chưa nhập tài khoản nào")
        async with async_session() as session:
            product = await repo.get_product(session, product_id)
            if not product:
                raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
            added = await repo.add_stock(session, product_id, lines, cost=cost)
            # Lấy danh sách chờ báo hàng rồi xoá -> gửi thông báo nền (không chặn response).
            waitlist = await repo.pop_waitlist_for_product(session, product_id)
            await session.commit()

        notified = 0
        if bot is not None and waitlist:
            # Chạy nền để admin không phải đợi gửi xong hàng loạt tin.
            asyncio.create_task(delivery.notify_restock(bot, product, waitlist))
            notified = len(waitlist)
        return {"added": added, "notified": notified}

    @router.patch("/api/stock/{item_id}")
    async def edit_stock(item_id: int, payload: dict = Body(...), admin_id: int = Depends(require_admin)):
        status = payload.get("status")
        if status is not None and status not in _STOCK_STATUSES:
            status = models.AVAILABLE
        cost = payload.get("cost")
        new_payload = payload.get("payload")
        async with async_session() as session:
            ok = await repo.update_stock_item(
                session, item_id,
                payload=new_payload.strip() if isinstance(new_payload, str) else None,
                status=status,
                cost=max(0, int(cost)) if cost is not None else None,
            )
            if not ok:
                raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
            await session.commit()
            item = await repo.get_stock_item(session, item_id)
            return {"item": _stock_dict(item)}

    @router.delete("/api/stock/{item_id}")
    async def delete_stock(item_id: int, admin_id: int = Depends(require_admin)):
        async with async_session() as session:
            product_id = await repo.delete_stock_item(session, item_id)
            await session.commit()
        if product_id is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
        return {"ok": True, "product_id": product_id}

    # ---------- Orders ----------

    @router.get("/api/orders")
    async def orders_list(status: str = "", admin_id: int = Depends(require_admin)):
        async with async_session() as session:
            orders = await repo.list_orders(session, limit=200, status=status or None)
            products = {p.id: p.name for p in await repo.list_products(session, only_active=False)}
        return {"orders": [_order_dict(o, products.get(o.product_id)) for o in orders]}

    @router.get("/api/orders/{order_id}")
    async def order_detail(order_id: int, admin_id: int = Depends(require_admin)):
        async with async_session() as session:
            order = await repo.get_order(session, order_id)
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn")
            product = await repo.get_product(session, order.product_id)
            items = await repo.get_order_items(session, order_id)
        is_upgrade = bool(product) and product.kind == models.KIND_UPGRADE
        order_cost = (order.cost or 0) if is_upgrade else sum(it.cost or 0 for it in items)
        return {
            "order": _order_dict(order, product.name if product else None),
            "product": _product_dict(product) if product else None,
            "is_upgrade": is_upgrade,
            "items": [_stock_dict(it) for it in items],
            "cost": order_cost,
            "profit": order.total_amount - order_cost,
        }

    @router.post("/api/orders/{order_id}/complete-upgrade")
    async def complete_upgrade(order_id: int, payload: dict = Body(default={}), admin_id: int = Depends(require_admin)):
        cost = max(0, int(payload.get("cost") or 0))
        notify = None
        async with async_session() as session:
            order = await repo.get_order(session, order_id)
            if not order:
                raise HTTPException(status_code=404, detail="Không tìm thấy đơn")
            if order.status == models.AWAITING_UPGRADE:
                await repo.complete_upgrade(session, order, cost=cost)
                await session.commit()
                notify = (order.buyer_tg_id, order.code, order.buyer_email)
            else:  # đã giao -> chỉ cập nhật giá vốn
                await repo.set_order_cost(session, order, cost)
                await session.commit()
            status = order.status
        if notify and bot is not None:
            tg_id, code, email = notify
            try:
                await bot.send_message(
                    tg_id,
                    f"🎉 Đơn <code>{code}</code> đã <b>nâng cấp xong</b> cho email "
                    f"<code>{html.escape(email or '')}</code>. Cảm ơn bạn đã mua hàng!",
                )
            except TelegramAPIError as exc:
                logger.error("Báo khách hoàn tất nâng cấp đơn %s thất bại: %s", code, exc)
        return {"ok": True, "status": status}

    # ---------- Users & wallet ----------

    @router.get("/api/users")
    async def users_list(admin_id: int = Depends(require_admin)):
        async with async_session() as session:
            users = await repo.list_users(session, limit=300)
        return {"users": [_user_dict(u) for u in users]}

    @router.get("/api/users/{tg_id}")
    async def user_detail(tg_id: int, admin_id: int = Depends(require_admin)):
        async with async_session() as session:
            user = await repo.get_user(session, tg_id)
            if user is None:
                raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
            txs = await repo.list_wallet_txs(session, tg_id, limit=100)
        return {"user": _user_dict(user), "txs": [_wallet_tx_dict(t) for t in txs]}

    @router.post("/api/users/{tg_id}/adjust")
    async def user_adjust(tg_id: int, payload: dict = Body(...), admin_id: int = Depends(require_admin)):
        """Cộng (amount>0) / trừ (amount<0) số dư ví của user."""
        try:
            amount = int(payload.get("amount") or 0)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Số tiền không hợp lệ")
        if amount == 0:
            raise HTTPException(status_code=422, detail="Số tiền phải khác 0")
        note = (payload.get("note") or "").strip()[:500]
        async with async_session() as session:
            ok, user = await repo.adjust_balance(session, tg_id, amount, note=note)
            if not ok:
                raise HTTPException(status_code=409, detail="Số dư không đủ để trừ")
            await session.commit()
            balance = user.balance
        # Báo cho user biết số dư thay đổi (nếu có bot).
        if bot is not None:
            verb = "cộng" if amount > 0 else "trừ"
            text = (
                f"🔔 Admin đã {verb} <b>{abs(amount):,}đ</b> vào ví của bạn.\n"
                f"Số dư hiện tại: <b>{balance:,}đ</b>."
            )
            if note:
                text += f"\nGhi chú: {html.escape(note)}"
            asyncio.create_task(_safe_send(bot, tg_id, text))
        return {"ok": True, "balance": balance}

    # ---------- Sold ----------

    @router.get("/api/sold")
    async def sold_list(admin_id: int = Depends(require_admin)):
        async with async_session() as session:
            rows_data = await repo.list_sold_items(session, limit=300)
        result = []
        for item, order, prod in rows_data:
            unit_sale = order.total_amount // order.quantity if order.quantity else 0
            result.append({
                "product_name": prod.name,
                "payload": item.payload,
                "order_id": order.id,
                "order_code": order.code,
                "unit_sale": unit_sale,
                "cost": item.cost or 0,
                "profit": unit_sale - (item.cost or 0),
                "paid_at": str(order.paid_at) if order.paid_at else None,
            })
        return {"sold": result}

    # ---------- SPA serving ----------
    # Phục vụ file tĩnh đã build; nếu không phải file cụ thể -> trả index.html cho client-router.
    # (APIRouter không hỗ trợ .mount() nên tự phục vụ file, kèm chặn path traversal.)

    @router.get("/{path:path}", response_class=HTMLResponse)
    async def spa(path: str = ""):
        if path:
            candidate = (_DIST_DIR / path).resolve()
            try:
                candidate.relative_to(_DIST_DIR.resolve())
            except ValueError:
                raise HTTPException(status_code=404, detail="Not found")
            if candidate.is_file():
                return FileResponse(str(candidate))
        if _INDEX_HTML.is_file():
            return FileResponse(str(_INDEX_HTML))
        return HTMLResponse(
            "<h1>Admin chưa được build</h1>"
            "<p>Chạy <code>cd admin &amp;&amp; npm install &amp;&amp; npm run build</code> rồi tải lại.</p>",
            status_code=503,
        )

    return router
