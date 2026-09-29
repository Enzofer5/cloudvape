"""Modelos del catálogo: categorías, marcas, productos, imágenes, descuentos y stock."""
from datetime import datetime

from ..extensions import db


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    products = db.relationship("Product", back_populates="category", lazy="dynamic")
    discounts = db.relationship("Discount", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Category {self.name}>"


class Brand(db.Model):
    __tablename__ = "brands"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    products = db.relationship("Product", back_populates="brand", lazy="dynamic")

    def __repr__(self):
        return f"<Brand {self.name}>"


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=False)
    sku = db.Column(db.String(40), nullable=False, unique=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(170), nullable=False, unique=True)
    short_description = db.Column(db.String(255))
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(12, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    min_stock = db.Column(db.Integer, nullable=False, default=5)
    nicotine_mg = db.Column(db.Numeric(5, 2))
    volume_ml = db.Column(db.Numeric(6, 2))
    puffs = db.Column(db.Integer)
    flavor = db.Column(db.String(80))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.CheckConstraint("price >= 0", name="ck_products_price"),
        db.CheckConstraint("stock >= 0", name="ck_products_stock"),
    )

    category = db.relationship("Category", back_populates="products")
    brand = db.relationship("Brand", back_populates="products")
    images = db.relationship(
        "ProductImage", back_populates="product", cascade="all, delete-orphan",
        order_by="(ProductImage.is_main.desc(), ProductImage.sort_order, ProductImage.id)",
    )
    discounts = db.relationship("Discount", back_populates="product", cascade="all, delete-orphan")
    stock_movements = db.relationship(
        "StockMovement", back_populates="product", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def main_image(self):
        return self.images[0] if self.images else None

    @property
    def in_stock(self) -> bool:
        return self.stock > 0

    @property
    def low_stock(self) -> bool:
        return self.stock <= self.min_stock

    def __repr__(self):
        return f"<Product {self.sku}>"


class ProductImage(db.Model):
    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    filename = db.Column(db.String(255), nullable=False, unique=True)
    sort_order = db.Column(db.SmallInteger, nullable=False, default=0)
    is_main = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    product = db.relationship("Product", back_populates="images")


class Discount(db.Model):
    __tablename__ = "discounts"

    PERCENT = "percent"
    FIXED = "fixed"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    discount_type = db.Column(db.Enum(PERCENT, FIXED, name="discount_type"), nullable=False)
    value = db.Column(db.Numeric(12, 2), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    product = db.relationship("Product", back_populates="discounts")
    category = db.relationship("Category", back_populates="discounts")

    @property
    def is_current(self) -> bool:
        now = datetime.now()
        return self.is_active and self.starts_at <= now <= self.ends_at

    @property
    def target_label(self) -> str:
        if self.product is not None:
            return f"Producto: {self.product.name}"
        if self.category is not None:
            return f"Categoría: {self.category.name}"
        return "-"

    @property
    def value_label(self) -> str:
        if self.discount_type == self.PERCENT:
            return f"{self.value:.0f}%"
        return f"$ {self.value:,.2f}"


class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    REASONS = {
        "initial": "Stock inicial",
        "purchase": "Compra a proveedor",
        "sale": "Venta",
        "adjustment": "Ajuste manual",
        "cancellation": "Cancelación de pedido",
    }

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="SET NULL"))
    change_qty = db.Column(db.Integer, nullable=False)
    reason = db.Column(
        db.Enum(*REASONS.keys(), name="stock_reason"), nullable=False
    )
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    product = db.relationship("Product", back_populates="stock_movements")
    user = db.relationship("User")
    order = db.relationship("Order")

    @property
    def reason_label(self) -> str:
        return self.REASONS.get(self.reason, self.reason)
