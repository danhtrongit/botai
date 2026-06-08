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
