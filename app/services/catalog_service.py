"""Consultas del catálogo público: búsqueda, filtros, orden y paginación."""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload

from ..extensions import db
from ..models import Brand, Category, Product

SORT_OPTIONS = {
    "newest": ("Más nuevos", Product.created_at.desc()),
    "price_asc": ("Menor precio", Product.price.asc()),
    "price_desc": ("Mayor precio", Product.price.desc()),
    "name": ("Nombre A-Z", Product.name.asc()),
}


def _escape_like(term: str) -> str:
    """Escapa comodines de LIKE; el valor igual viaja como parámetro (sin SQL injection)."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _to_decimal(value):
    try:
        d = Decimal(str(value))
        return d if d >= 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


@dataclass
class CatalogFilters:
    q: str = ""
    category: str = ""
    brands: list[int] = field(default_factory=list)
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    nicotine: str = ""  # "0", "low", "high"
    in_stock: bool = False
    sort: str = "newest"

    @classmethod
    def from_args(cls, args) -> "CatalogFilters":
        brands = []
        for b in args.getlist("brand"):
            if str(b).isdigit():
                brands.append(int(b))
        sort = args.get("sort", "newest")
        return cls(
            q=(args.get("q") or "").strip()[:100],
            category=(args.get("category") or "").strip()[:100],
            brands=brands,
            min_price=_to_decimal(args.get("min_price")) if args.get("min_price") else None,
            max_price=_to_decimal(args.get("max_price")) if args.get("max_price") else None,
            nicotine=args.get("nicotine", "") if args.get("nicotine") in ("0", "low", "high") else "",
            in_stock=args.get("in_stock") == "1",
            sort=sort if sort in SORT_OPTIONS else "newest",
        )


def base_query():
    return (
        Product.query
        .join(Category).join(Brand)
        .filter(Product.is_active.is_(True), Category.is_active.is_(True), Brand.is_active.is_(True))
        .options(selectinload(Product.images), joinedload(Product.brand), joinedload(Product.category))
    )


def search_products(filters: CatalogFilters, page: int, per_page: int):
    query = base_query()

    if filters.q:
        like = f"%{_escape_like(filters.q)}%"
        query = query.filter(or_(
            Product.name.ilike(like, escape="\\"),
            Product.short_description.ilike(like, escape="\\"),
            Product.flavor.ilike(like, escape="\\"),
            Product.sku.ilike(like, escape="\\"),
            Brand.name.ilike(like, escape="\\"),
        ))
    if filters.category:
        query = query.filter(Category.slug == filters.category)
    if filters.brands:
        query = query.filter(Product.brand_id.in_(filters.brands))
    if filters.min_price is not None:
        query = query.filter(Product.price >= filters.min_price)
    if filters.max_price is not None:
        query = query.filter(Product.price <= filters.max_price)
    if filters.nicotine == "0":
        query = query.filter(or_(Product.nicotine_mg.is_(None), Product.nicotine_mg == 0))
    elif filters.nicotine == "low":
        query = query.filter(Product.nicotine_mg > 0, Product.nicotine_mg <= 20)
    elif filters.nicotine == "high":
        query = query.filter(Product.nicotine_mg > 20)
    if filters.in_stock:
        query = query.filter(Product.stock > 0)

    query = query.order_by(SORT_OPTIONS[filters.sort][1], Product.id.desc())
    return db.paginate(query, page=page, per_page=per_page, error_out=False)


def featured_products(limit=8):
    return (base_query().filter(Product.is_featured.is_(True))
            .order_by(Product.created_at.desc()).limit(limit).all())


def latest_products(limit=8):
    return base_query().order_by(Product.created_at.desc()).limit(limit).all()


def get_product_by_slug(slug: str):
    return base_query().filter(Product.slug == slug).first()


def related_products(product: Product, limit=4):
    return (base_query()
            .filter(Product.category_id == product.category_id, Product.id != product.id)
            .order_by(db.func.random() if db.engine.dialect.name == "sqlite" else db.func.rand())
            .limit(limit).all())


def active_categories():
    return Category.query.filter_by(is_active=True).order_by(Category.name).all()


def active_brands():
    return Brand.query.filter_by(is_active=True).order_by(Brand.name).all()
