"""Modelos de carrito y pedidos."""
from datetime import datetime
from decimal import Decimal

from ..extensions import db


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),
        db.CheckConstraint("quantity > 0", name="ck_cart_quantity"),
    )

    user = db.relationship("User", back_populates="cart_items")
    product = db.relationship("Product")


class OrderStatus(db.Model):
    __tablename__ = "order_statuses"

    PENDING = "pending"
    PAID = "paid"
    PREPARING = "preparing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

    # Transiciones permitidas (máquina de estados)
    TRANSITIONS = {
        PENDING: {PAID, CANCELLED},
        PAID: {PREPARING, CANCELLED},
        PREPARING: {SHIPPED, CANCELLED},
        SHIPPED: {DELIVERED},
        DELIVERED: set(),
        CANCELLED: set(),
    }

    id = db.Column(db.SmallInteger, primary_key=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    name = db.Column(db.String(40), nullable=False)
    sort_order = db.Column(db.SmallInteger, nullable=False, default=0)

    def can_transition_to(self, target_code: str) -> bool:
        return target_code in self.TRANSITIONS.get(self.code, set())

    def __repr__(self):
        return f"<OrderStatus {self.code}>"


class Order(db.Model):
    __tablename__ = "orders"

    PAYMENT_METHODS = {
        "transfer": "Transferencia bancaria",
        "cash": "Efectivo al retirar / contra entrega",
        "card": "Tarjeta (al recibir)",
    }

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status_id = db.Column(db.SmallInteger, db.ForeignKey("order_statuses.id"), nullable=False)
    payment_method = db.Column(db.Enum(*PAYMENT_METHODS.keys(), name="payment_method"), nullable=False)
    shipping_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    recipient_name = db.Column(db.String(120), nullable=False)
    recipient_phone = db.Column(db.String(30), nullable=False)
    ship_street = db.Column(db.String(120), nullable=False)
    ship_number = db.Column(db.String(10), nullable=False)
    ship_apartment = db.Column(db.String(20))
    ship_city = db.Column(db.String(80), nullable=False)
    ship_province = db.Column(db.String(80), nullable=False)
    ship_postal_code = db.Column(db.String(10), nullable=False)
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    user = db.relationship("User", back_populates="orders")
    status = db.relationship("OrderStatus")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    history = db.relationship(
        "OrderStatusHistory", back_populates="order", cascade="all, delete-orphan",
        order_by="OrderStatusHistory.created_at",
    )

    # Totales calculados (no se almacenan: 3FN)
    @property
    def subtotal(self) -> Decimal:
        return sum((i.line_total for i in self.items), Decimal("0"))

    @property
    def discount_total(self) -> Decimal:
        return sum(((i.list_price - i.unit_price) * i.quantity for i in self.items), Decimal("0"))

    @property
    def total(self) -> Decimal:
        return self.subtotal + (self.shipping_cost or Decimal("0"))

    @property
    def items_count(self) -> int:
        return sum(i.quantity for i in self.items)

    @property
    def payment_label(self) -> str:
        return self.PAYMENT_METHODS.get(self.payment_method, self.payment_method)

    @property
    def shipping_address(self) -> str:
        apt = f" {self.ship_apartment}" if self.ship_apartment else ""
        return (f"{self.ship_street} {self.ship_number}{apt}, {self.ship_city}, "
                f"{self.ship_province} ({self.ship_postal_code})")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    product_name = db.Column(db.String(150), nullable=False)
    list_price = db.Column(db.Numeric(12, 2), nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product"),
        db.CheckConstraint("quantity > 0", name="ck_order_items_qty"),
    )

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


class OrderStatusHistory(db.Model):
    __tablename__ = "order_status_history"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    status_id = db.Column(db.SmallInteger, db.ForeignKey("order_statuses.id"), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    comment = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    order = db.relationship("Order", back_populates="history")
    status = db.relationship("OrderStatus")
    user = db.relationship("User")
