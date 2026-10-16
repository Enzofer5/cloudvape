"""ABM de productos, imágenes, stock y precios."""
from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from ...extensions import db
from ...forms.admin import BulkPriceForm, ConfirmForm, ProductForm, StockAdjustForm
from ...models import Brand, Category, Product, ProductImage, StockMovement
from ...services import product_service
from ...services.catalog_service import _escape_like
from ...services.product_service import ProductError
from ...utils.helpers import page_arg
from ...utils.uploads import InvalidImageError
from . import bp


def _fill_choices(form):
    cats = Category.query.order_by(Category.name).all()
    brands = Brand.query.order_by(Brand.name).all()
    if hasattr(form, "category_id"):
        form.category_id.choices = [(c.id, c.name) for c in cats]
    if hasattr(form, "brand_id"):
        form.brand_id.choices = [(b.id, b.name) for b in brands]
    return cats, brands


def _get_product(product_id) -> Product:
    product = db.session.get(Product, product_id)
    if product is None:
        abort(404)
    return product


def _form_data(form) -> dict:
    return {f: getattr(form, f).data for f in product_service.EDITABLE_FIELDS} | {"stock": form.stock.data}


@bp.route("/productos")
def products():
    q = (request.args.get("q") or "").strip()
    category_id = request.args.get("category", type=int)
    brand_id = request.args.get("brand", type=int)
    status = request.args.get("status", "")

    query = Product.query.options(joinedload(Product.category), joinedload(Product.brand))
    if q:
        like = f"%{_escape_like(q)}%"
        query = query.filter(or_(Product.name.ilike(like, escape="\\"), Product.sku.ilike(like, escape="\\")))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if brand_id:
        query = query.filter(Product.brand_id == brand_id)
    if status == "active":
        query = query.filter(Product.is_active.is_(True))
    elif status == "inactive":
        query = query.filter(Product.is_active.is_(False))
    elif status == "low_stock":
        query = query.filter(Product.stock <= Product.min_stock)

    pagination = db.paginate(query.order_by(Product.created_at.desc()), page=page_arg(),
                             per_page=current_app.config["ADMIN_ITEMS_PER_PAGE"], error_out=False)
    cats = Category.query.order_by(Category.name).all()
    brands = Brand.query.order_by(Brand.name).all()
    args = request.args.to_dict()
    args.pop("page", None)
    return render_template("admin/products/list.html", pagination=pagination, categories=cats, brands=brands,
                           confirm_form=ConfirmForm(), query_args=args)


@bp.route("/productos/nuevo", methods=["GET", "POST"])
def product_new():
    form = ProductForm()
    _fill_choices(form)
    if form.validate_on_submit():
        try:
            product = product_service.create_product(_form_data(form), form.images.data, current_user)
        except (ProductError, InvalidImageError) as exc:
            flash(str(exc), "danger")
        else:
            flash("Producto creado.", "success")
            return redirect(url_for("admin.product_edit", product_id=product.id))
    return render_template("admin/products/form.html", form=form, product=None)


@bp.route("/productos/<int:product_id>", methods=["GET", "POST"])
def product_edit(product_id):
    product = _get_product(product_id)
    form = ProductForm(obj=product)
    _fill_choices(form)
    del form.stock  # el stock se modifica solo con movimientos auditados
    if form.validate_on_submit():
        data = {f: getattr(form, f).data for f in product_service.EDITABLE_FIELDS}
        try:
            product_service.update_product(product, data, form.images.data)
        except (ProductError, InvalidImageError) as exc:
            flash(str(exc), "danger")
        else:
            flash("Producto actualizado.", "success")
            return redirect(url_for("admin.product_edit", product_id=product.id))
    return render_template("admin/products/form.html", form=form, product=product, confirm_form=ConfirmForm())


@bp.route("/productos/<int:product_id>/eliminar", methods=["POST"])
def product_delete(product_id):
    if not ConfirmForm().validate_on_submit():
        abort(400)
    result = product_service.delete_product(_get_product(product_id))
    if result == "deleted":
        flash("Producto eliminado.", "info")
    else:
        flash("El producto tiene ventas registradas: se desactivó en lugar de eliminarse.", "warning")
    return redirect(url_for("admin.products"))


@bp.route("/imagenes/<int:image_id>/eliminar", methods=["POST"])
def image_delete(image_id):
    if not ConfirmForm().validate_on_submit():
        abort(400)
    image = db.session.get(ProductImage, image_id) or abort(404)
    product_id = image.product_id
    product_service.delete_image(image)
    flash("Imagen eliminada.", "info")
    return redirect(url_for("admin.product_edit", product_id=product_id))


@bp.route("/imagenes/<int:image_id>/principal", methods=["POST"])
def image_main(image_id):
    if not ConfirmForm().validate_on_submit():
        abort(400)
    image = db.session.get(ProductImage, image_id) or abort(404)
    product_service.set_main_image(image)
    flash("Imagen principal actualizada.", "success")
    return redirect(url_for("admin.product_edit", product_id=image.product_id))


# ------------------------------- Stock -------------------------------
@bp.route("/productos/<int:product_id>/stock", methods=["GET", "POST"])
def product_stock(product_id):
    product = _get_product(product_id)
    form = StockAdjustForm()
    if form.validate_on_submit():
        try:
            product_service.adjust_stock(product, form.change_qty.data, form.reason.data,
                                         current_user, form.note.data)
        except ProductError as exc:
            flash(str(exc), "danger")
        else:
            flash("Movimiento de stock registrado.", "success")
            return redirect(url_for("admin.product_stock", product_id=product.id))
    movements = product.stock_movements.order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).limit(100).all()
    return render_template("admin/products/stock.html", product=product, form=form, movements=movements)


@bp.route("/stock")
def stock_overview():
    products = (Product.query.options(joinedload(Product.brand))
                .filter(Product.stock <= Product.min_stock)
                .order_by(Product.stock, Product.name).all())
    return render_template("admin/products/stock_overview.html", products=products)


# ------------------------------ Precios ------------------------------
@bp.route("/precios", methods=["GET", "POST"])
def prices():
    form = BulkPriceForm()
    _fill_choices(form)
    form.category_id.choices = [(0, "Todas")] + form.category_id.choices
    form.brand_id.choices = [(0, "Todas")] + form.brand_id.choices
    if form.validate_on_submit():
        try:
            n = product_service.bulk_update_prices(form.percent.data, form.category_id.data or None,
                                                   form.brand_id.data or None)
        except ProductError as exc:
            flash(str(exc), "danger")
        else:
            flash(f"Se actualizaron los precios de {n} productos.", "success")
            return redirect(url_for("admin.prices"))
    return render_template("admin/products/prices.html", form=form)
