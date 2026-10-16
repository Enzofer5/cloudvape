"""Carrito de compras.

- Visitantes: el carrito vive en la sesión firmada ({product_id: cantidad}).
- Clientes logueados: se persiste en la tabla cart_items.
Al iniciar sesión, el carrito de la sesión se fusiona con el de la base.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from flask import current_app, session
from flask_login import current_user

from ..extensions import db
from ..models import CartItem, Product
from .pricing_service import price_info

SESSION_KEY = "cart"
MAX_QTY_PER_ITEM = 20


class CartError(Exception):
    pass


@dataclass
class CartLine:
    product: Product
    quantity: int
    unit_list_price: Decimal
    unit_price: Decimal

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity

    @property
    def line_discount(self) -> Decimal:
        return (self.unit_list_price - self.unit_price) * self.quantity


@dataclass
class CartSummary:
    lines: list[CartLine] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    shipping_cost: Decimal = Decimal("0")

    @property
    def subtotal(self) -> Decimal:
        return sum((l.line_total for l in self.lines), Decimal("0"))

    @property
    def discount_total(self) -> Decimal:
        return sum((l.line_discount for l in self.lines), Decimal("0"))

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.shipping_cost

    @property
    def count(self) -> int:
        return sum(l.quantity for l in self.lines)

    @property
    def is_empty(self) -> bool:
        return not self.lines


def _use_db() -> bool:
    return current_user.is_authenticated and not current_user.is_admin


# ------------------------------------------------------------------
# Lectura / escritura del almacenamiento
# ------------------------------------------------------------------
def _read() -> dict[int, int]:
    if _use_db():
        return {ci.product_id: ci.quantity for ci in CartItem.query.filter_by(user_id=current_user.id)}
    raw = session.get(SESSION_KEY, {})
    return {int(k): int(v) for k, v in raw.items() if str(k).isdigit()}


def _write(product_id: int, quantity: int) -> None:
    if _use_db():
        item = CartItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        if quantity <= 0:
            if item:
                db.session.delete(item)
        elif item:
            item.quantity = quantity
        else:
            db.session.add(CartItem(user_id=current_user.id, product_id=product_id, quantity=quantity))
        db.session.commit()
    else:
        cart = dict(session.get(SESSION_KEY, {}))
        if quantity <= 0:
            cart.pop(str(product_id), None)
        else:
            cart[str(product_id)] = quantity
        session[SESSION_KEY] = cart
        session.modified = True


def _get_sellable_product(product_id: int) -> Product:
    product = db.session.get(Product, product_id)
    if not product or not product.is_active or not product.category.is_active or not product.brand.is_active:
        raise CartError("El producto no está disponible.")
    return product


# ------------------------------------------------------------------
# Operaciones públicas
# ------------------------------------------------------------------
def add(product_id: int, quantity: int = 1) -> None:
    if quantity < 1:
        raise CartError("Cantidad inválida.")
    product = _get_sellable_product(product_id)
    current = _read().get(product_id, 0)
    new_qty = current + quantity
    if new_qty > product.stock:
        raise CartError(f"Solo hay {product.stock} unidades disponibles de {product.name}.")
    if new_qty > MAX_QTY_PER_ITEM:
        raise CartError(f"Máximo {MAX_QTY_PER_ITEM} unidades por producto.")
    _write(product_id, new_qty)


def update(product_id: int, quantity: int) -> None:
    if quantity <= 0:
        _write(product_id, 0)
        return
    product = _get_sellable_product(product_id)
    if quantity > product.stock:
        raise CartError(f"Solo hay {product.stock} unidades disponibles de {product.name}.")
    if quantity > MAX_QTY_PER_ITEM:
        raise CartError(f"Máximo {MAX_QTY_PER_ITEM} unidades por producto.")
    _write(product_id, quantity)


def remove(product_id: int) -> None:
    _write(product_id, 0)


def clear() -> None:
    if _use_db():
        CartItem.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
    session.pop(SESSION_KEY, None)


def count() -> int:
    return sum(_read().values())


def merge_session_cart_into_user(user) -> None:
    """Se llama justo después del login."""
    raw = session.pop(SESSION_KEY, {}) or {}
    if not raw or user.is_admin:
        return
    for pid_str, qty in raw.items():
        if not str(pid_str).isdigit():
            continue
        pid = int(pid_str)
        product = db.session.get(Product, pid)
        if not product or not product.is_active:
            continue
        item = CartItem.query.filter_by(user_id=user.id, product_id=pid).first()
        new_qty = min((item.quantity if item else 0) + int(qty), product.stock, MAX_QTY_PER_ITEM)
        if new_qty <= 0:
            continue
        if item:
            item.quantity = new_qty
        else:
            db.session.add(CartItem(user_id=user.id, product_id=pid, quantity=new_qty))
    db.session.commit()


def shipping_for(subtotal: Decimal) -> Decimal:
    cfg = current_app.config
    if subtotal <= 0:
        return Decimal("0")
    if subtotal >= Decimal(str(cfg["FREE_SHIPPING_FROM"])):
        return Decimal("0")
    return Decimal(str(cfg["SHIPPING_FLAT_COST"])).quantize(Decimal("0.01"))


def get_summary() -> CartSummary:
    """Arma el detalle del carrito revalidando disponibilidad, stock y precios actuales."""
    raw = _read()
    summary = CartSummary()
    if not raw:
        return summary

    products = {p.id: p for p in Product.query.filter(Product.id.in_(raw.keys())).all()}
    for pid, qty in raw.items():
        product = products.get(pid)
        if not product or not product.is_active or not product.category.is_active or not product.brand.is_active:
            summary.warnings.append("Se quitó del carrito un producto que ya no está disponible.")
            _write(pid, 0)
            continue
        if product.stock <= 0:
            summary.warnings.append(f"{product.name} se quedó sin stock y fue removido.")
            _write(pid, 0)
            continue
        if qty > product.stock:
            summary.warnings.append(f"Ajustamos {product.name} a {product.stock} unidades por stock disponible.")
            qty = product.stock
            _write(pid, qty)
        info = price_info(product)
        summary.lines.append(CartLine(product, qty, info.list_price, info.final_price))

    summary.lines.sort(key=lambda l: l.product.name)
    summary.shipping_cost = shipping_for(summary.subtotal)
    return summary
