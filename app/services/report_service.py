"""Estadísticas del dashboard y reportes de ventas (agregaciones en SQL)."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from ..extensions import db
from ..models import (Brand, Category, Order, OrderItem, OrderStatus, Product,
                      Role, User)
from ..utils.helpers import day_end, day_start


def _items_totals_subquery():
    return (
        select(
            OrderItem.order_id.label("order_id"),
            func.sum(OrderItem.unit_price * OrderItem.quantity).label("subtotal"),
            func.sum((OrderItem.list_price - OrderItem.unit_price) * OrderItem.quantity).label("discount"),
            func.sum(OrderItem.quantity).label("units"),
        )
        .group_by(OrderItem.order_id)
        .subquery()
    )


def _valid_orders_filter(start: datetime, end: datetime):
    return (Order.created_at >= start, Order.created_at <= end,
            OrderStatus.code != OrderStatus.CANCELLED)


@dataclass
class SalesTotals:
    orders: int
    revenue: Decimal
    discounts: Decimal
    units: int

    @property
    def avg_ticket(self) -> Decimal:
        return (self.revenue / self.orders).quantize(Decimal("0.01")) if self.orders else Decimal("0")


def sales_totals(start: datetime, end: datetime) -> SalesTotals:
    it = _items_totals_subquery()
    row = db.session.execute(
        select(
            func.count(Order.id),
            func.coalesce(func.sum(it.c.subtotal + Order.shipping_cost), 0),
            func.coalesce(func.sum(it.c.discount), 0),
            func.coalesce(func.sum(it.c.units), 0),
        )
        .join(it, it.c.order_id == Order.id)
        .join(OrderStatus, OrderStatus.id == Order.status_id)
        .where(*_valid_orders_filter(start, end))
    ).one()
    return SalesTotals(int(row[0]), Decimal(row[1]), Decimal(row[2]), int(row[3]))


def sales_by_day(start: date, end: date) -> list[dict]:
    it = _items_totals_subquery()
    day = func.date(Order.created_at)
    rows = db.session.execute(
        select(day, func.count(Order.id), func.sum(it.c.subtotal + Order.shipping_cost))
        .join(it, it.c.order_id == Order.id)
        .join(OrderStatus, OrderStatus.id == Order.status_id)
        .where(*_valid_orders_filter(day_start(start), day_end(end)))
        .group_by(day).order_by(day)
    ).all()
    data = {str(r[0]): (int(r[1]), Decimal(r[2] or 0)) for r in rows}
    result, cur = [], start
    while cur <= end:  # rellena días sin ventas con cero
        orders, revenue = data.get(cur.isoformat(), (0, Decimal("0")))
        result.append({"date": cur.isoformat(), "orders": orders, "revenue": revenue})
        cur += timedelta(days=1)
    return result


def top_products(start: datetime, end: datetime, limit=10) -> list[dict]:
    units = func.sum(OrderItem.quantity)
    revenue = func.sum(OrderItem.unit_price * OrderItem.quantity)
    rows = db.session.execute(
        select(Product.id, Product.sku, Product.name, units.label("units"), revenue.label("revenue"))
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(OrderStatus, OrderStatus.id == Order.status_id)
        .where(*_valid_orders_filter(start, end))
        .group_by(Product.id, Product.sku, Product.name)
        .order_by(units.desc()).limit(limit)
    ).all()
    return [{"id": r.id, "sku": r.sku, "name": r.name, "units": int(r.units),
             "revenue": Decimal(r.revenue)} for r in rows]


def sales_by_category(start: datetime, end: datetime) -> list[dict]:
    revenue = func.sum(OrderItem.unit_price * OrderItem.quantity)
    rows = db.session.execute(
        select(Category.name, func.sum(OrderItem.quantity), revenue)
        .join(Product, Product.category_id == Category.id)
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(OrderStatus, OrderStatus.id == Order.status_id)
        .where(*_valid_orders_filter(start, end))
        .group_by(Category.name).order_by(revenue.desc())
    ).all()
    return [{"name": r[0], "units": int(r[1]), "revenue": Decimal(r[2])} for r in rows]


def sales_by_brand(start: datetime, end: datetime) -> list[dict]:
    revenue = func.sum(OrderItem.unit_price * OrderItem.quantity)
    rows = db.session.execute(
        select(Brand.name, func.sum(OrderItem.quantity), revenue)
        .join(Product, Product.brand_id == Brand.id)
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(OrderStatus, OrderStatus.id == Order.status_id)
        .where(*_valid_orders_filter(start, end))
        .group_by(Brand.name).order_by(revenue.desc())
    ).all()
    return [{"name": r[0], "units": int(r[1]), "revenue": Decimal(r[2])} for r in rows]


def orders_in_range(start: datetime, end: datetime, status_code: str | None = None):
    q = (Order.query.options(selectinload(Order.items), joinedload(Order.user), joinedload(Order.status))
         .join(OrderStatus, OrderStatus.id == Order.status_id)
         .filter(Order.created_at >= start, Order.created_at <= end))
    if status_code:
        q = q.filter(OrderStatus.code == status_code)
    return q.order_by(Order.created_at.desc()).all()


def orders_by_status() -> list[tuple]:
    return db.session.execute(
        select(OrderStatus.code, OrderStatus.name, func.count(Order.id))
        .outerjoin(Order, Order.status_id == OrderStatus.id)
        .group_by(OrderStatus.id, OrderStatus.code, OrderStatus.name, OrderStatus.sort_order)
        .order_by(OrderStatus.sort_order)
    ).all()


def dashboard_data() -> dict:
    today = date.today()
    month_start = today.replace(day=1)
    last30 = today - timedelta(days=29)

    customers_q = User.query.join(Role).filter(Role.name == Role.CUSTOMER)
    return {
        "today": sales_totals(day_start(today), day_end(today)),
        "month": sales_totals(day_start(month_start), day_end(today)),
        "customers_total": customers_q.count(),
        "customers_new_month": customers_q.filter(User.created_at >= day_start(month_start)).count(),
        "products_active": Product.query.filter_by(is_active=True).count(),
        "low_stock": (Product.query.filter(Product.is_active.is_(True), Product.stock <= Product.min_stock)
                      .order_by(Product.stock).limit(10).all()),
        "recent_orders": (Order.query.options(selectinload(Order.items), joinedload(Order.user),
                                              joinedload(Order.status))
                          .order_by(Order.created_at.desc()).limit(8).all()),
        "status_counts": orders_by_status(),
        "series": sales_by_day(last30, today),
        "top_products": top_products(day_start(last30), day_end(today), 5),
    }
