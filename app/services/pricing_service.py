"""Cálculo de precios con descuentos vigentes.

Los descuentos activos se cargan una sola vez por request (cache en flask.g)
para evitar el problema de N+1 consultas al listar productos.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from flask import g

from ..models import Discount

TWO = Decimal("0.01")


@dataclass(frozen=True)
class PriceInfo:
    list_price: Decimal
    final_price: Decimal
    discount: Discount | None

    @property
    def has_discount(self) -> bool:
        return self.final_price < self.list_price

    @property
    def percent_off(self) -> int:
        if not self.has_discount or self.list_price == 0:
            return 0
        return int(((self.list_price - self.final_price) / self.list_price * 100).quantize(Decimal("1")))


def _active_discounts():
    if "active_discounts" not in g:
        now = datetime.now()
        rows = Discount.query.filter(
            Discount.is_active.is_(True),
            Discount.starts_at <= now,
            Discount.ends_at >= now,
        ).all()
        by_product, by_category = {}, {}
        for d in rows:
            if d.product_id:
                by_product.setdefault(d.product_id, []).append(d)
            else:
                by_category.setdefault(d.category_id, []).append(d)
        g.active_discounts = (by_product, by_category)
    return g.active_discounts


def apply_discount(price: Decimal, discount: Discount) -> Decimal:
    price = Decimal(price)
    if discount.discount_type == Discount.PERCENT:
        result = price * (Decimal("100") - Decimal(discount.value)) / Decimal("100")
    else:
        result = price - Decimal(discount.value)
    return max(result, Decimal("0")).quantize(TWO, rounding=ROUND_HALF_UP)


def price_info(product) -> PriceInfo:
    """Devuelve el mejor precio vigente para el producto (el descuento más conveniente)."""
    list_price = Decimal(product.price).quantize(TWO)
    by_product, by_category = _active_discounts()
    candidates = by_product.get(product.id, []) + by_category.get(product.category_id, [])

    best_price, best_discount = list_price, None
    for d in candidates:
        p = apply_discount(list_price, d)
        if p < best_price:
            best_price, best_discount = p, d
    return PriceInfo(list_price, best_price, best_discount)


def invalidate_cache() -> None:
    g.pop("active_discounts", None)
