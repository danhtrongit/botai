from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# Order statuses
PENDING = "pending"
PAID = "paid"
DELIVERED = "delivered"
AWAITING_UPGRADE = "awaiting_upgrade"  # đã trả tiền, chờ admin nâng cấp thủ công
EXPIRED = "expired"
FAILED = "failed"

# StockItem statuses
AVAILABLE = "available"
RESERVED = "reserved"
SOLD = "sold"

# Product kinds
KIND_ACCOUNT = "account"  # giao tài khoản từ kho (mặc định)
KIND_UPGRADE = "upgrade"  # nâng cấp chính chủ: khách nhập email, admin xử lý tay

# WalletTx types
TX_TOPUP = "topup"            # khách nạp tiền (qua QR, admin duyệt)
TX_ADMIN_CREDIT = "admin_credit"  # admin cộng tiền tay
TX_ADMIN_DEBIT = "admin_debit"    # admin trừ tiền tay
TX_PURCHASE = "purchase"      # trừ tiền khi mua hàng bằng ví
TX_REFUND = "refund"          # hoàn tiền

# WalletTx statuses (chỉ 'confirmed' mới ảnh hưởng số dư)
TX_PENDING = "pending"
TX_CONFIRMED = "confirmed"
TX_REJECTED = "rejected"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(2000), default="")
    price: Mapped[int] = mapped_column(BigInteger)  # VND
    kind: Mapped[str] = mapped_column(String(20), default=KIND_ACCOUNT)  # account | upgrade
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    stock_items: Mapped[list["StockItem"]] = relationship(back_populates="product")


class StockItem(Base):
    __tablename__ = "stock_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    payload: Mapped[str] = mapped_column(String(1000))  # vd "user|pass"
    cost: Mapped[int] = mapped_column(BigInteger, default=0)  # giá vốn theo từng TK (VND)
    status: Mapped[str] = mapped_column(String(20), default=AVAILABLE, index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    product: Mapped["Product"] = relationship(back_populates="stock_items")


class AppSetting(Base):
    """Key-value lưu cấu hình runtime (vd thông tin đăng nhập MBBank đã mã hoá)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(4000))


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    buyer_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    buyer_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    buyer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)  # đơn nâng cấp
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column()
    total_amount: Mapped[int] = mapped_column(BigInteger)
    cost: Mapped[int] = mapped_column(BigInteger, default=0)  # giá vốn đơn nâng cấp (đơn TK lấy từ StockItem)
    status: Mapped[str] = mapped_column(String(20), default=PENDING, index=True)
    payment_tx_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class User(Base):
    """Người dùng bot + số dư ví (VND). tg_id là khoá chính."""

    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    balance: Mapped[int] = mapped_column(BigInteger, default=0)  # số dư ví (VND)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class WalletTx(Base):
    """Sổ giao dịch ví. Chỉ bản ghi status='confirmed' mới phản ánh vào số dư."""

    __tablename__ = "wallet_txs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int] = mapped_column(BigInteger)  # dương = cộng, âm = trừ
    type: Mapped[str] = mapped_column(String(20))    # topup|admin_credit|admin_debit|purchase|refund
    status: Mapped[str] = mapped_column(String(20), default=TX_CONFIRMED, index=True)
    note: Mapped[str] = mapped_column(String(500), default="")
    ref_code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    balance_after: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class StockWaitlist(Base):
    """Danh sách chờ báo hàng: user đăng ký nhận thông báo khi SP có hàng trở lại."""

    __tablename__ = "stock_waitlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
