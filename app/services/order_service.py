"""Checkout y ciclo de vida de pedidos.

El checkout corre en una única transacción y bloquea las filas de productos
(SELECT ... FOR UPDATE) para que dos compras simultáneas no vendan el mismo stock.
"""
import secrets
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (Address, CartItem, Order, OrderItem, OrderStatus,
                      OrderStatusHistory, Product, StockMovement)
from . import cart_service
from .pricing_service import price_info


class OrderError(Exception):
    pass


def get_status(code: str) -> OrderStatus:
    return OrderStatus.query.filter_by(code=code).one()


def all_statuses():
    return OrderStatus.query.order_by(OrderStatus.sort_order).all()


def _generate_order_number() -> str:
    while True:
        number = f"CV-{datetime.now():%y%m%d}-{secrets.token_hex(3).upper()}"
        if not Order.query.filter_by(order_number=number).first():
            return number


def place_order(user, data: dict) -> Order:
    """data: recipient_name, recipient_phone, street, street_number, apartment, city,
    province, postal_code, payment_method, notes, save_address (bool)."""
    summary = cart_service.get_summary()
    if summary.is_empty:
        raise OrderError("Tu carrito está vacío.")
    if summary.warnings:
        raise OrderError("Tu carrito cambió por disponibilidad de stock. Revisalo antes de confirmar.")
    if data.get("payment_method") not in Order.PAYMENT_METHODS:
        raise OrderError("Medio de pago inválido.")

    quantities = {line.product.id: line.quantity for line in summary.lines}

    try:
        # Bloqueo pesimista de las filas involucradas, en orden de id para evitar deadlocks
        locked = (Product.query.filter(Product.id.in_(quantities.keys()))
                  .order_by(Product.id).with_for_update().all())
        locked_by_id = {p.id: p for p in locked}

        order = Order(
            order_number=_generate_order_number(),
            user_id=user.id,
            status=get_status(OrderStatus.PENDING),
            payment_method=data["payment_method"],
            recipient_name=data["recipient_name"].strip(),
            recipient_phone=data["recipient_phone"].strip(),
            ship_street=data["street"].strip(),
            ship_number=data["street_number"].strip(),
            ship_apartment=(data.get("apartment") or "").strip() or None,
            ship_city=data["city"].strip(),
            ship_province=data["province"].strip(),
            ship_postal_code=data["postal_code"].strip(),
            notes=(data.get("notes") or "").strip() or None,
        )
        db.session.add(order)

        for pid, qty in quantities.items():
            product = locked_by_id.get(pid)
            if product is None or not product.is_active:
                raise OrderError("Un producto del carrito ya no está disponible.")
            if product.stock < qty:
                raise OrderError(f"Stock insuficiente para {product.name} (disponible: {product.stock}).")
            info = price_info(product)
            order.items.append(OrderItem(
                product_id=product.id,
                product_name=product.name,
                list_price=info.list_price,
                unit_price=info.final_price,
                quantity=qty,
            ))
            product.stock -= qty
            db.session.add(StockMovement(
                product_id=product.id, user_id=user.id, order=order,
                change_qty=-qty, reason="sale", note=f"Pedido {order.order_number}",
            ))

        order.shipping_cost = cart_service.shipping_for(
            sum((i.unit_price * i.quantity for i in order.items), 0)
        )
        order.history.append(OrderStatusHistory(
            status=order.status, changed_by=user.id, comment="Pedido creado por el cliente",
        ))

        if data.get("save_address"):
            has_default = any(a.is_default for a in user.addresses)
            db.session.add(Address(
                user_id=user.id, label="Envío",
                street=order.ship_street, street_number=order.ship_number,
                apartment=order.ship_apartment, city=order.ship_city,
                province=order.ship_province, postal_code=order.ship_postal_code,
                is_default=not has_default,
            ))

        CartItem.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        return order
    except OrderError:
        db.session.rollback()
        raise
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise OrderError("No pudimos procesar el pedido. Intentá nuevamente.") from exc


def _restore_stock(order: Order, user_id) -> None:
    for item in order.items:
        product = db.session.get(Product, item.product_id, with_for_update=True)
        product.stock += item.quantity
        db.session.add(StockMovement(
            product_id=product.id, user_id=user_id, order_id=order.id,
            change_qty=item.quantity, reason="cancellation",
            note=f"Cancelación pedido {order.order_number}",
        ))


def change_status(order: Order, target_code: str, changed_by, comment: str | None = None) -> None:
    if not order.status.can_transition_to(target_code):
        raise OrderError(f"No se puede pasar de '{order.status.name}' a ese estado.")
    target = get_status(target_code)
    try:
        if target_code == OrderStatus.CANCELLED:
            _restore_stock(order, changed_by.id if changed_by else None)
        order.status = target
        order.history.append(OrderStatusHistory(
            status=target, changed_by=changed_by.id if changed_by else None,
            comment=(comment or "").strip() or None,
        ))
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise OrderError("No se pudo actualizar el estado del pedido.") from exc


def cancel_by_customer(order: Order, user) -> None:
    if order.user_id != user.id:
        raise OrderError("Pedido inexistente.")
    if order.status.code != OrderStatus.PENDING:
        raise OrderError("Solo podés cancelar pedidos pendientes de pago.")
    change_status(order, OrderStatus.CANCELLED, user, "Cancelado por el cliente")


def get_customer_order(user, order_number: str) -> Order | None:
    return (Order.query.options(selectinload(Order.items), selectinload(Order.history))
            .filter_by(user_id=user.id, order_number=order_number).first())


def customer_orders(user, page: int, per_page: int = 10):
    q = (Order.query.options(selectinload(Order.items))
         .filter_by(user_id=user.id).order_by(Order.created_at.desc()))
    return db.paginate(q, page=page, per_page=per_page, error_out=False)
