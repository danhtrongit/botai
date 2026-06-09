from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import get_settings
from bot.db.models import KIND_UPGRADE, Product

# Nhãn nút bàn phím cố định (dùng chung cho keyboard + filter handler).
BTN_BUY = "🛒 Mua hàng"
BTN_ORDERS = "📦 Đơn của tôi"
BTN_HELP = "ℹ️ Trợ giúp"


def reply_menu() -> ReplyKeyboardMarkup:
    """Bàn phím nút bấm cố định hiển thị dưới khung chat."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BUY)],
            [KeyboardButton(text=BTN_ORDERS), KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Chọn 🛒 Mua hàng để bắt đầu",
    )


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Mua hàng", callback_data="menu:buy")
    kb.button(text="💰 Ví của tôi", callback_data="menu:wallet")
    kb.button(text="📦 Đơn của tôi", callback_data="menu:orders")
    kb.button(text="ℹ️ Trợ giúp", callback_data="menu:help")
    kb.button(text="🆘 Liên hệ hỗ trợ", url=get_settings().support_url)
    kb.adjust(1)
    return kb.as_markup()


def product_list(products: list[tuple[Product, int]]) -> InlineKeyboardMarkup:
    """products: list (product, available_count)."""
    kb = InlineKeyboardBuilder()
    for product, available in products:
        if product.kind == KIND_UPGRADE:
            suffix = "nâng cấp chính chủ"
        else:
            suffix = f"còn {available}"
        kb.button(
            text=f"{product.name} — {product.price:,}đ ({suffix})",
            callback_data=f"prod:{product.id}",
        )
    kb.button(text="⬅️ Về menu", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def cancel_to_home() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Chọn sản phẩm khác", callback_data="menu:buy")
    kb.adjust(1)
    return kb.as_markup()


def quantity_keyboard(product_id: int, qty: int, max_qty: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="➖", callback_data=f"qty:{product_id}:dec"),
        InlineKeyboardButton(text=f"{qty}", callback_data="noop"),
        InlineKeyboardButton(text="➕", callback_data=f"qty:{product_id}:inc"),
    )
    presets = [n for n in (1, 5, 10) if n <= max_qty]
    if presets:
        kb.row(*[InlineKeyboardButton(text=str(n), callback_data=f"qtyset:{product_id}:{n}") for n in presets])
    kb.row(InlineKeyboardButton(text="✅ Xác nhận mua", callback_data=f"qtyok:{product_id}"))
    kb.row(InlineKeyboardButton(text="⬅️ Chọn sản phẩm khác", callback_data="menu:buy"))
    return kb.as_markup()


def payment_keyboard(order_id: int, can_pay_wallet: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if can_pay_wallet:
        kb.button(text="💳 Thanh toán bằng số dư", callback_data=f"paywallet:{order_id}")
    kb.button(text="✅ Tôi đã chuyển khoản", callback_data=f"ipaid:{order_id}")
    kb.button(text="❌ Hủy đơn", callback_data=f"ordercancel:{order_id}")
    kb.button(text="🆘 Liên hệ hỗ trợ", url=get_settings().support_url)
    kb.adjust(1)
    return kb.as_markup()


def admin_review_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Nút admin duyệt đơn: Chấp nhận / Từ chối."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Chấp nhận", callback_data=f"adm_ok:{order_id}")
    kb.button(text="❌ Từ chối", callback_data=f"adm_no:{order_id}")
    kb.adjust(2)
    return kb.as_markup()


def wallet_menu(balance: int) -> InlineKeyboardMarkup:
    """Menu ví: nạp tiền / lịch sử."""
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Nạp tiền", callback_data="wallet:topup")
    kb.button(text="📜 Lịch sử giao dịch", callback_data="wallet:history")
    kb.button(text="⬅️ Về menu", callback_data="menu:home")
    kb.adjust(1)
    return kb.as_markup()


def topup_payment_keyboard(code: str) -> InlineKeyboardMarkup:
    """Màn QR nạp tiền: khách báo đã CK / huỷ."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tôi đã chuyển khoản", callback_data=f"topup_paid:{code}")
    kb.button(text="🆘 Liên hệ hỗ trợ", url=get_settings().support_url)
    kb.adjust(1)
    return kb.as_markup()


def admin_topup_keyboard(code: str) -> InlineKeyboardMarkup:
    """Nút admin duyệt nạp ví: Chấp nhận / Từ chối."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Chấp nhận", callback_data=f"topup_ok:{code}")
    kb.button(text="❌ Từ chối", callback_data=f"topup_no:{code}")
    kb.adjust(2)
    return kb.as_markup()


def restock_subscribe_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """SP hết hàng: cho phép đăng ký nhận báo khi có hàng."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🔔 Báo khi có hàng", callback_data=f"notifyme:{product_id}")
    kb.button(text="⬅️ Chọn sản phẩm khác", callback_data="menu:buy")
    kb.adjust(1)
    return kb.as_markup()
