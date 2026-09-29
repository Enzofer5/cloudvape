"""Administración de productos, imágenes, stock y precios."""
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.exc import IntegrityError
from werkzeug.datastructures import FileStorage

from ..extensions import db
from ..models import OrderItem, Product, ProductImage, StockMovement
from ..utils.helpers import unique_slug
from ..utils.uploads import delete_product_image_file, save_product_image

EDITABLE_FIELDS = (
    "category_id", "brand_id", "sku", "name", "short_description", "description",
    "price", "min_stock", "nicotine_mg", "volume_ml", "puffs", "flavor",
    "is_active", "is_featured",
)


class ProductError(Exception):
    pass


def _apply_fields(product: Product, data: dict) -> None:
    for f in EDITABLE_FIELDS:
        if f in data:
            value = data[f]
            if isinstance(value, str):
                value = value.strip() or None if f not in ("sku", "name") else value.strip()
            setattr(product, f, value)
    product.sku = product.sku.upper()


def create_product(data: dict, images, user) -> Product:
    product = Product()
    _apply_fields(product, data)
    product.slug = unique_slug(Product, product.name)
    initial_stock = int(data.get("stock") or 0)
    product.stock = initial_stock
    db.session.add(product)
    try:
        db.session.flush()
        if initial_stock > 0:
            db.session.add(StockMovement(product_id=product.id, user_id=user.id,
                                         change_qty=initial_stock, reason="initial"))
        _add_images(product, images)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ProductError("Ya existe un producto con ese SKU.") from exc
    return product


def update_product(product: Product, data: dict, images) -> Product:
    old_name = product.name
    _apply_fields(product, data)
    if product.name != old_name:
        product.slug = unique_slug(Product, product.name, exclude_id=product.id)
    try:
        _add_images(product, images)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ProductError("Ya existe un producto con ese SKU.") from exc
    return product


def _add_images(product: Product, images) -> None:
    files = [f for f in (images or []) if isinstance(f, FileStorage) and f.filename]
    if not files:
        return
    start = max([img.sort_order for img in product.images] or [0]) + 1
    has_main = any(img.is_main for img in product.images)
    for i, f in enumerate(files):
        filename = save_product_image(f)  # lanza InvalidImageError si no es válida
        product.images.append(ProductImage(
            filename=filename, sort_order=start + i, is_main=(not has_main and i == 0),
        ))


def delete_image(image: ProductImage) -> None:
    product = image.product
    was_main = image.is_main
    filename = image.filename
    product.images.remove(image)
    db.session.flush()
    if was_main and product.images:
        product.images[0].is_main = True
    db.session.commit()
    delete_product_image_file(filename)


def set_main_image(image: ProductImage) -> None:
    for img in image.product.images:
        img.is_main = img.id == image.id
    db.session.commit()


def delete_product(product: Product) -> str:
    """Borra físicamente si nunca se vendió; si tiene ventas, solo lo desactiva
    (preserva la integridad del historial de pedidos)."""
    sold = db.session.query(OrderItem.id).filter_by(product_id=product.id).first()
    if sold:
        product.is_active = False
        db.session.commit()
        return "deactivated"
    filenames = [img.filename for img in product.images]
    db.session.delete(product)
    db.session.commit()
    for fn in filenames:
        delete_product_image_file(fn)
    return "deleted"


def adjust_stock(product: Product, change_qty: int, reason: str, user, note: str | None = None) -> None:
    if change_qty == 0:
        raise ProductError("La cantidad debe ser distinta de cero.")
    if reason not in ("purchase", "adjustment"):
        raise ProductError("Motivo inválido.")
    locked = db.session.get(Product, product.id, with_for_update=True)
    if locked.stock + change_qty < 0:
        db.session.rollback()
        raise ProductError(f"El stock no puede quedar negativo (actual: {locked.stock}).")
    locked.stock += change_qty
    db.session.add(StockMovement(product_id=locked.id, user_id=user.id, change_qty=change_qty,
                                 reason=reason, note=(note or "").strip() or None))
    db.session.commit()


def bulk_update_prices(percent: Decimal, category_id=None, brand_id=None) -> int:
    """Aumenta/disminuye precios en un porcentaje, filtrando por categoría y/o marca."""
    if percent == 0 or percent <= -100:
        raise ProductError("Porcentaje inválido.")
    q = Product.query
    if category_id:
        q = q.filter(Product.category_id == category_id)
    if brand_id:
        q = q.filter(Product.brand_id == brand_id)
    factor = (Decimal("100") + percent) / Decimal("100")
    count = 0
    for p in q.all():
        p.price = (Decimal(p.price) * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        count += 1
    db.session.commit()
    return count
