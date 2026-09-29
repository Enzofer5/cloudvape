"""Tienda pública: portada, catálogo, búsqueda y detalle de producto."""
from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from ..services import catalog_service
from ..services.catalog_service import SORT_OPTIONS, CatalogFilters
from ..utils.helpers import page_arg

bp = Blueprint("shop", __name__)


@bp.route("/")
def index():
    return render_template(
        "shop/index.html",
        featured=catalog_service.featured_products(8),
        latest=catalog_service.latest_products(8),
        categories=catalog_service.active_categories(),
    )


@bp.route("/productos")
def catalog():
    filters = CatalogFilters.from_args(request.args)
    pagination = catalog_service.search_products(
        filters, page_arg(), current_app.config["PRODUCTS_PER_PAGE"]
    )
    # parámetros actuales (sin 'page') para armar los links de paginación
    args = request.args.to_dict(flat=False)
    args.pop("page", None)
    return render_template(
        "shop/catalog.html",
        pagination=pagination,
        filters=filters,
        categories=catalog_service.active_categories(),
        brands=catalog_service.active_brands(),
        sort_options={k: v[0] for k, v in SORT_OPTIONS.items()},
        query_args=args,
    )


@bp.route("/categoria/<slug>")
def category(slug):
    return redirect(url_for("shop.catalog", category=slug))


@bp.route("/producto/<slug>")
def product_detail(slug):
    product = catalog_service.get_product_by_slug(slug)
    if product is None:
        abort(404)
    return render_template(
        "shop/product.html",
        product=product,
        related=catalog_service.related_products(product),
    )


@bp.route("/terminos")
def terms():
    return render_template("shop/terms.html")
