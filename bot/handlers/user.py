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
from bot.services import delivery, payment, wallet
from bot.states import BuyFlow, TopUpFlow

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
        "Sau khi chuyển khoản, bấm <b>✅ Tôi đã chuyển khoản</b> để admin xác nhận. "
        "Khi được duyệt, admin sẽ nâng cấp cho email của bạn (thường trong ít phút)."
        if is_upgrade
        else "Sau khi chuyển khoản, bấm <b>✅ Tôi đã chuyển khoản</b> để admin xác nhận. "
        "Khi được duyệt, hệ thống sẽ gửi tài khoản cho bạn ngay."
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
    # Ghi nhận user để có trong danh sách (ví, thông báo...).
    async with async_session() as session:
        await repo.upsert_user(session, message.from_user.id, message.from_user.username)
        await session.commit()
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
        # Hết hàng -> cho phép đăng ký nhận báo khi có hàng trở lại.
        await callback.message.edit_text(
            f"<b>{product.name}</b> hiện đã hết hàng.\n\n"
            "Bấm 🔔 <b>Báo khi có hàng</b> để được nhắn ngay khi có hàng trở lại.",
            reply_markup=keyboards.restock_subscribe_keyboard(product_id),
        )
        await callback.answer()
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

    # Nếu đủ số dư ví -> hiện thêm nút thanh toán bằng số dư.
    async with async_session() as session:
        wallet_user = await repo.get_user(session, user.id)
    can_wallet = bool(wallet_user) and wallet_user.balance >= order.total_amount

    caption = _payment_caption(order, is_upgrade=False)
    await callback.message.answer_photo(
        photo=result.qr_url, caption=caption,
        reply_markup=keyboards.payment_keyboard(order.id, can_pay_wallet=can_wallet),
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

    # SP nâng cấp cũng có thể thanh toán bằng ví nếu đủ số dư.
    async with async_session() as session:
        wallet_user = await repo.get_user(session, user.id)
    can_wallet = bool(wallet_user) and wallet_user.balance >= order.total_amount

    caption = _payment_caption(order, is_upgrade=True, email=email)
    await message.answer_photo(
        photo=result.qr_url, caption=caption,
        reply_markup=keyboards.payment_keyboard(order.id, can_pay_wallet=can_wallet),
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


@router.callback_query(F.data.startswith("ipaid:"))
async def cb_order_paid(callback: CallbackQuery) -> None:
    """Khách báo đã chuyển khoản -> gửi admin duyệt tay (Chấp nhận / Từ chối)."""
    order_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        order = await repo.get_order(session, order_id)
        if not order or order.buyer_tg_id != callback.from_user.id:
            await callback.answer("Không tìm thấy đơn.", show_alert=True)
            return
        if order.status != models.PENDING:
            await callback.answer("Đơn đã được xử lý hoặc hết hạn.", show_alert=True)
            return
        product = await repo.get_product(session, order.product_id)
        is_upgrade = bool(product) and product.kind == models.KIND_UPGRADE

    await delivery.notify_admins_review(callback.bot, order, is_upgrade=is_upgrade)
    await callback.answer(
        "Đã gửi yêu cầu xác nhận tới admin. Vui lòng chờ duyệt (thường trong ít phút).",
        show_alert=True,
    )


@router.callback_query(F.data == "menu:orders")
async def cb_my_orders(callback: CallbackQuery) -> None:
    text, markup = await _orders_view(callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


# ---------------- Ví người dùng ----------------

_TX_LABEL = {
    models.TX_TOPUP: "Nạp tiền",
    models.TX_ADMIN_CREDIT: "Admin cộng",
    models.TX_ADMIN_DEBIT: "Admin trừ",
    models.TX_PURCHASE: "Mua hàng",
    models.TX_REFUND: "Hoàn tiền",
}


async def _wallet_text(user_id: int, username: str | None) -> tuple[str, object]:
    async with async_session() as session:
        user = await repo.upsert_user(session, user_id, username)
        balance = user.balance
        await session.commit()
    text = (
        "💰 <b>Ví của tôi</b>\n\n"
        f"Số dư hiện tại: <b>{_fmt_vnd(balance)}</b>\n\n"
        "Nạp tiền để thanh toán nhanh, không cần chuyển khoản từng đơn."
    )
    return text, keyboards.wallet_menu(balance)


@router.callback_query(F.data == "menu:wallet")
async def cb_wallet(callback: CallbackQuery) -> None:
    text, markup = await _wallet_text(callback.from_user.id, callback.from_user.username)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "wallet:history")
async def cb_wallet_history(callback: CallbackQuery) -> None:
    async with async_session() as session:
        txs = await repo.list_wallet_txs(session, callback.from_user.id, limit=15)
    if not txs:
        await callback.answer("Chưa có giao dịch nào.", show_alert=True)
        return
    lines = ["📜 <b>Lịch sử giao dịch ví</b>\n"]
    for tx in txs:
        sign = "➕" if tx.amount >= 0 else "➖"
        label = _TX_LABEL.get(tx.type, tx.type)
        status = "" if tx.status == models.TX_CONFIRMED else f" ({tx.status})"
        lines.append(f"{sign} {_fmt_vnd(abs(tx.amount))} — {label}{status}")
    await callback.message.edit_text("\n".join(lines), reply_markup=keyboards.wallet_menu(0))
    await callback.answer()


@router.callback_query(F.data == "wallet:topup")
async def cb_wallet_topup(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TopUpFlow.entering_amount)
    await callback.message.edit_text(
        "➕ <b>Nạp tiền vào ví</b>\n\n"
        f"Nhập số tiền muốn nạp (VND), tối thiểu {_fmt_vnd(wallet.MIN_TOPUP)}.\n"
        "Ví dụ: <code>100000</code>",
        reply_markup=keyboards.cancel_to_home(),
    )
    await callback.answer()


@router.message(TopUpFlow.entering_amount)
async def msg_topup_amount(message: Message, state: FSMContext) -> None:
    raw = re.sub(r"[^\d]", "", message.text or "")
    if not raw:
        await message.answer("⚠️ Vui lòng nhập số tiền hợp lệ (chỉ số). Ví dụ: <code>100000</code>")
        return
    amount = int(raw)
    user = message.from_user
    try:
        async with async_session() as session:
            req = await wallet.request_topup(
                session, tg_id=user.id, username=user.username, amount=amount
            )
    except wallet.InvalidAmount:
        await message.answer(
            f"⚠️ Số tiền phải từ {_fmt_vnd(wallet.MIN_TOPUP)} đến {_fmt_vnd(wallet.MAX_TOPUP)}."
        )
        return

    await state.set_state(TopUpFlow.awaiting_topup_payment)
    await state.update_data(topup_code=req.code)
    caption = (
        "💰 <b>Nạp ví</b>\n"
        f"Số tiền: <b>{_fmt_vnd(amount)}</b>\n\n"
        "Quét QR dưới đây để chuyển khoản.\n"
        f"<b>Nội dung chuyển khoản phải là:</b> <code>{payment.order_note(req.code)}</code>\n\n"
        "Sau khi chuyển, bấm <b>✅ Tôi đã chuyển khoản</b> để admin xác nhận cộng tiền."
    )
    await message.answer_photo(
        photo=req.qr_url, caption=caption, reply_markup=keyboards.topup_payment_keyboard(req.code)
    )


@router.callback_query(F.data.startswith("topup_paid:"))
async def cb_topup_paid(callback: CallbackQuery) -> None:
    """Khách báo đã chuyển khoản nạp ví -> gửi admin duyệt."""
    code = callback.data.split(":", 1)[1]
    async with async_session() as session:
        tx = await repo.get_wallet_tx_by_code(session, code)
        if tx is None or tx.user_tg_id != callback.from_user.id:
            await callback.answer("Không tìm thấy yêu cầu nạp.", show_alert=True)
            return
        if tx.status != models.TX_PENDING:
            await callback.answer("Yêu cầu đã được xử lý.", show_alert=True)
            return
        user = await repo.get_user(session, callback.from_user.id)

    await delivery.notify_admins_topup_review(callback.bot, tx, user)
    await callback.answer(
        "Đã gửi yêu cầu nạp tới admin. Vui lòng chờ duyệt (thường trong ít phút).",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("paywallet:"))
async def cb_pay_wallet(callback: CallbackQuery, state: FSMContext) -> None:
    """Thanh toán đơn bằng số dư ví -> giao ngay."""
    await callback.answer("Đang xử lý...")
    order_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        order = await repo.get_order(session, order_id)
        if not order or order.buyer_tg_id != callback.from_user.id:
            await callback.answer("Không tìm thấy đơn.", show_alert=True)
            return
        user = await repo.get_user(session, callback.from_user.id)
        result = await order_service.pay_with_wallet(session, order, user)

    if not result.ok:
        if result.reason == "insufficient":
            await callback.answer("Số dư không đủ. Vui lòng nạp thêm hoặc chuyển khoản.", show_alert=True)
        else:
            await callback.answer("Đơn đã được xử lý hoặc hết hạn.", show_alert=True)
        return

    await state.clear()
    try:
        await callback.message.edit_caption(
            caption=f"✅ Đã thanh toán đơn <code>{order.code}</code> bằng số dư ví."
        )
    except Exception:  # noqa: BLE001
        pass

    if result.delivered:
        await delivery.deliver(callback.bot, order, result.payloads)
    elif result.awaiting_upgrade:
        await delivery.notify_upgrade_pending(callback.bot, order)


@router.callback_query(F.data.startswith("notifyme:"))
async def cb_notify_me(callback: CallbackQuery) -> None:
    """Đăng ký nhận thông báo khi SP có hàng trở lại."""
    product_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        await repo.upsert_user(session, callback.from_user.id, callback.from_user.username)
        added = await repo.add_to_waitlist(session, callback.from_user.id, product_id)
        await session.commit()
    if added:
        await callback.answer("🔔 Đã đăng ký! Bạn sẽ được nhắn ngay khi có hàng.", show_alert=True)
    else:
        await callback.answer("Bạn đã đăng ký nhận báo hàng sản phẩm này rồi.", show_alert=True)

