from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import keyboards
from bot.config import get_settings
from bot.db import models, repo
from bot.db.database import async_session
from bot.services import orders as order_service
from bot.services import payment
from bot.states import BuyFlow

router = Router(name="user")

WELCOME = (
    "👋 Chào mừng bạn đến cửa hàng tài khoản digital!\n\n"
    "Bấm <b>🛒 Mua hàng</b> để chọn sản phẩm và thanh toán nhanh qua chuyển khoản (QR)."
)

HELP = (
    "ℹ️ <b>Hướng dẫn</b>\n\n"
    "1. Bấm 🛒 Mua hàng → chọn sản phẩm → chọn số lượng.\n"
    "2. Quét mã QR (hoặc chuyển khoản đúng số tiền + nội dung).\n"
    "3. Hệ thống tự xác nhận và gửi tài khoản cho bạn ngay tại đây.\n\n"
    "Đơn chưa thanh toán sẽ tự hết hạn sau một thời gian và hoàn lại kho.\n\n"
    "🆘 Cần hỗ trợ? Liên hệ @ncp_ai"
)


def _fmt_vnd(amount: int) -> str:
    return f"{amount:,}đ".replace(",", ".")


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(text: str) -> bool:
    return bool(_EMAIL_RE.match((text or "").strip()))


def _payment_caption(order, *, is_upgrade: bool, email: str | None = None) -> str:
    head = f"🧾 <b>Đơn {order.code}</b>"
    if is_upgrade:
        head += " (Nâng cấp chính chủ)\n" + f"Email nâng cấp: <code>{email}</code>\n"
    else:
        head += f"\nSố lượng: <b>{order.quantity}</b>\n"
    tail_action = (
        "Sau khi chuyển đủ tiền, admin sẽ nâng cấp cho email của bạn (thường trong ít phút)."
        if is_upgrade
        else "Sau khi chuyển đủ tiền, hệ thống sẽ tự động gửi tài khoản cho bạn (thường trong vài giây)."
    )
    return (
        f"{head}"
        f"Số tiền: <b>{_fmt_vnd(order.total_amount)}</b>\n\n"
        f"Vui lòng chuyển khoản theo QR dưới đây.\n"
        f"<b>Nội dung chuyển khoản phải là:</b> <code>{payment.order_note(order.code)}</code>\n\n"
        f"{tail_action}"
    )


# ---- View builders dùng chung cho cả lệnh, nút bàn phím và nút inline ----

async def _products_view() -> tuple[str, object]:
    async with async_session() as session:
        products = await repo.list_products(session, only_active=True)
        rows = [(p, await repo.count_available(session, p.id)) for p in products]
    if not rows:
        return "Hiện chưa có sản phẩm nào. Vui lòng quay lại sau!", keyboards.main_menu()
    return "🛒 Chọn sản phẩm:", keyboards.product_list(rows)


async def _orders_view(user_id: int) -> tuple[str, object]:
    async with async_session() as session:
        orders = await repo.list_orders_by_buyer(session, user_id, limit=10)
    if not orders:
        return "Bạn chưa có đơn hàng nào.", keyboards.main_menu()
    lines = ["📦 <b>Đơn gần đây của bạn:</b>\n"]
    for o in orders:
        lines.append(f"<code>{o.code}</code> — SL {o.quantity} — {_fmt_vnd(o.total_amount)} — {o.status}")
    return "\n".join(lines), keyboards.main_menu()


# ---- Lệnh & nút bàn phím cố định (quick menu) ----

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    # Bàn phím nút bấm cố định dưới khung chat để user luôn biết bấm gì.
    await message.answer(WELCOME, reply_markup=keyboards.reply_menu())
    await message.answer("Chọn thao tác:", reply_markup=keyboards.main_menu())


async def _send_products(message: Message, state: FSMContext) -> None:
    await state.clear()
    text, markup = await _products_view()
    await message.answer(text, reply_markup=markup)


async def _send_orders(message: Message) -> None:
    text, markup = await _orders_view(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.message(Command("mua"))
async def cmd_mua(message: Message, state: FSMContext) -> None:
    await _send_products(message, state)


@router.message(F.text == keyboards.BTN_BUY)
async def txt_mua(message: Message, state: FSMContext) -> None:
    await _send_products(message, state)


@router.message(Command("donhang"))
async def cmd_donhang(message: Message) -> None:
    await _send_orders(message)


@router.message(F.text == keyboards.BTN_ORDERS)
async def txt_donhang(message: Message) -> None:
    await _send_orders(message)


@router.message(Command("trogiup"))
async def cmd_trogiup(message: Message) -> None:
    await message.answer(HELP, reply_markup=keyboards.main_menu())


@router.message(F.text == keyboards.BTN_HELP)
async def txt_trogiup(message: Message) -> None:
    await message.answer(HELP, reply_markup=keyboards.main_menu())


@router.callback_query(F.data == "menu:home")
async def cb_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(WELCOME, reply_markup=keyboards.main_menu())
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: CallbackQuery) -> None:
    await callback.message.edit_text(HELP, reply_markup=keyboards.main_menu())
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "menu:buy")
async def cb_buy(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    text, markup = await _products_view()
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith("prod:"))
async def cb_select_product(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        product = await repo.get_product(session, product_id)
        is_upgrade = bool(product) and product.kind == models.KIND_UPGRADE
        available = 0 if is_upgrade else (await repo.count_available(session, product_id) if product else 0)
    if not product or not product.is_active:
        await callback.answer("Sản phẩm không khả dụng.", show_alert=True)
        return

    if is_upgrade:
        # SP nâng cấp chính chủ: không có kho, cố định 1 đơn vị, cần email khách.
        await state.set_state(BuyFlow.entering_email)
        await state.update_data(product_id=product_id)
        desc = f"\n\n{product.description}" if product.description else ""
        text = (
            f"<b>{product.name}</b> (Nâng cấp chính chủ){desc}\n\n"
            f"Giá: <b>{_fmt_vnd(product.price)}</b>\n\n"
            f"✉️ Vui lòng nhập <b>email cần nâng cấp</b> của bạn (gõ và gửi vào khung chat):"
        )
        await callback.message.edit_text(text, reply_markup=keyboards.cancel_to_home())
        await callback.answer()
        return

    if available <= 0:
        await callback.answer("Sản phẩm đã hết hàng.", show_alert=True)
        return

    await state.set_state(BuyFlow.choosing_quantity)
    await state.update_data(product_id=product_id, qty=1, max_qty=available)
    desc = f"\n\n{product.description}" if product.description else ""
    text = (
        f"<b>{product.name}</b>{desc}\n\n"
        f"Giá: <b>{_fmt_vnd(product.price)}</b>/tài khoản\n"
        f"Còn lại: <b>{available}</b>\n\n"
        f"Chọn số lượng:"
    )
    await callback.message.edit_text(
        text, reply_markup=keyboards.quantity_keyboard(product_id, 1, available)
    )
    await callback.answer()


async def _render_quantity(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    product_id = data["product_id"]
    qty = data["qty"]
    max_qty = data["max_qty"]
    await callback.message.edit_reply_markup(
        reply_markup=keyboards.quantity_keyboard(product_id, qty, max_qty)
    )


@router.callback_query(F.data.startswith("qty:"))
async def cb_qty_step(callback: CallbackQuery, state: FSMContext) -> None:
    _, _pid, direction = callback.data.split(":")
    data = await state.get_data()
    qty = data.get("qty", 1)
    max_qty = data.get("max_qty", 1)
    if direction == "inc":
        qty = min(max_qty, qty + 1)
    else:
        qty = max(1, qty - 1)
    await state.update_data(qty=qty)
    await _render_quantity(callback, state)
    await callback.answer()


@router.callback_query(F.data.startswith("qtyset:"))
async def cb_qty_set(callback: CallbackQuery, state: FSMContext) -> None:
    _, _pid, n = callback.data.split(":")
    data = await state.get_data()
    max_qty = data.get("max_qty", 1)
    qty = max(1, min(max_qty, int(n)))
    await state.update_data(qty=qty)
    await _render_quantity(callback, state)
    await callback.answer()


@router.callback_query(F.data.startswith("qtyok:"))
async def cb_qty_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    product_id = data.get("product_id")
    qty = data.get("qty", 1)
    if not product_id:
        await callback.answer("Phiên đã hết hạn, vui lòng chọn lại.", show_alert=True)
        return

    user = callback.from_user
    async with async_session() as session:
        try:
            result = await order_service.create_order(
                session,
                buyer_tg_id=user.id,
                buyer_username=user.username,
                product_id=product_id,
                quantity=qty,
            )
        except order_service.OutOfStock as exc:
            await callback.answer(f"Không đủ hàng (còn {exc.available}).", show_alert=True)
            return
        except order_service.ProductUnavailable:
            await callback.answer("Sản phẩm không khả dụng.", show_alert=True)
            return

    order = result.order
    await state.set_state(BuyFlow.awaiting_payment)
    await state.update_data(order_id=order.id)

    caption = _payment_caption(order, is_upgrade=False)
    await callback.message.answer_photo(
        photo=result.qr_url, caption=caption, reply_markup=keyboards.payment_keyboard(order.id)
    )
    await callback.answer()


@router.message(BuyFlow.entering_email)
async def msg_enter_email(message: Message, state: FSMContext) -> None:
    """Khách nhập email cho đơn nâng cấp chính chủ -> tạo đơn + hiện QR."""
    email = (message.text or "").strip()
    if not valid_email(email):
        await message.answer(
            "⚠️ Email chưa hợp lệ. Vui lòng nhập đúng định dạng, ví dụ <code>ten@email.com</code>:",
            reply_markup=keyboards.cancel_to_home(),
        )
        return

    data = await state.get_data()
    product_id = data.get("product_id")
    if not product_id:
        await message.answer("Phiên đã hết hạn, vui lòng chọn lại sản phẩm.", reply_markup=keyboards.main_menu())
        await state.clear()
        return

    user = message.from_user
    async with async_session() as session:
        try:
            result = await order_service.create_order(
                session,
                buyer_tg_id=user.id,
                buyer_username=user.username,
                product_id=product_id,
                quantity=1,
                buyer_email=email,
            )
        except order_service.ProductUnavailable:
            await message.answer("Sản phẩm không khả dụng.", reply_markup=keyboards.main_menu())
            await state.clear()
            return

    order = result.order
    await state.set_state(BuyFlow.awaiting_payment)
    await state.update_data(order_id=order.id)

    caption = _payment_caption(order, is_upgrade=True, email=email)
    await message.answer_photo(
        photo=result.qr_url, caption=caption, reply_markup=keyboards.payment_keyboard(order.id)
    )


@router.callback_query(F.data.startswith("ordercancel:"))
async def cb_order_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    order_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        order = await repo.get_order(session, order_id)
        if not order or order.buyer_tg_id != callback.from_user.id:
            await callback.answer("Không tìm thấy đơn.", show_alert=True)
            return
        if order.status != models.PENDING:
            await callback.answer("Đơn không thể hủy (đã xử lý hoặc hết hạn).", show_alert=True)
            return
        await order_service.cancel_order(session, order)
    await state.clear()
    await callback.message.edit_caption(caption=f"❌ Đơn {order.code} đã bị hủy.")
    await callback.answer("Đã hủy đơn.")


@router.callback_query(F.data.startswith("ordercheck:"))
async def cb_order_check(callback: CallbackQuery) -> None:
    order_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        order = await repo.get_order(session, order_id)
    if not order or order.buyer_tg_id != callback.from_user.id:
        await callback.answer("Không tìm thấy đơn.", show_alert=True)
        return
    status_text = {
        models.PENDING: "⏳ Chưa nhận được thanh toán. Vui lòng chuyển khoản đúng nội dung & số tiền.",
        models.PAID: "✅ Đã nhận thanh toán, đang giao hàng...",
        models.AWAITING_UPGRADE: "✅ Đã nhận thanh toán, admin đang nâng cấp cho email của bạn.",
        models.DELIVERED: "✅ Đơn đã hoàn tất.",
        models.EXPIRED: "❌ Đơn đã hết hạn/đã hủy.",
        models.FAILED: "⚠️ Đơn gặp sự cố, vui lòng liên hệ admin.",
    }.get(order.status, order.status)
    await callback.answer(status_text, show_alert=True)


@router.callback_query(F.data == "menu:orders")
async def cb_my_orders(callback: CallbackQuery) -> None:
    text, markup = await _orders_view(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()
