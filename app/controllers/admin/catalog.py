"""ABM de categorías, marcas y descuentos."""
from flask import abort, flash, redirect, render_template, url_for
from sqlalchemy.exc import IntegrityError

from ...extensions import db
from ...forms.admin import BrandForm, CategoryForm, ConfirmForm, DiscountForm
from ...models import Brand, Category, Discount, Product
from ...utils.helpers import unique_slug
from . import bp


def _get_or_404(model, obj_id):
    obj = db.session.get(model, obj_id)
    if obj is None:
        abort(404)
    return obj


def _save_named(model, obj, form, list_endpoint, label):
    """Alta/modificación común para entidades con nombre + slug (categorías y marcas)."""
    is_new = obj is None
    with db.session.no_autoflush:
        if is_new:
            obj = model()
        form.populate_obj(obj)
        obj.name = obj.name.strip()
        obj.slug = unique_slug(model, obj.name, exclude_id=None if is_new else obj.id)
    if is_new:
        db.session.add(obj)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        form.name.errors.append(f"Ya existe una {label} con ese nombre.")
        return None
    flash(f"{label.capitalize()} guardada.", "success")
    return redirect(url_for(list_endpoint))


def _delete_named(model, obj_id, list_endpoint, label):
    if not ConfirmForm().validate_on_submit():
        abort(400)
    obj = _get_or_404(model, obj_id)
    if obj.products.count():
        flash(f"No se puede eliminar: la {label} tiene productos asociados. Podés desactivarla.", "danger")
    else:
        db.session.delete(obj)
        db.session.commit()
        flash(f"{label.capitalize()} eliminada.", "info")
    return redirect(url_for(list_endpoint))


# ----------------------------- Categorías -----------------------------
@bp.route("/categorias")
def categories():
    items = Category.query.order_by(Category.name).all()
    counts = {c.id: c.products.count() for c in items}
    return render_template("admin/categories/list.html", items=items, counts=counts, confirm_form=ConfirmForm())


@bp.route("/categorias/nueva", methods=["GET", "POST"])
@bp.route("/categorias/<int:category_id>", methods=["GET", "POST"])
def category_form(category_id=None):
    obj = _get_or_404(Category, category_id) if category_id else None
    form = CategoryForm(obj=obj)
    if form.validate_on_submit():
        resp = _save_named(Category, obj, form, "admin.categories", "categoría")
        if resp:
            return resp
    return render_template("admin/categories/form.html", form=form, obj=obj)


@bp.route("/categorias/<int:category_id>/eliminar", methods=["POST"])
def category_delete(category_id):
    return _delete_named(Category, category_id, "admin.categories", "categoría")


# ------------------------------- Marcas -------------------------------
@bp.route("/marcas")
def brands():
    items = Brand.query.order_by(Brand.name).all()
    counts = {b.id: b.products.count() for b in items}
    return render_template("admin/brands/list.html", items=items, counts=counts, confirm_form=ConfirmForm())


@bp.route("/marcas/nueva", methods=["GET", "POST"])
@bp.route("/marcas/<int:brand_id>", methods=["GET", "POST"])
def brand_form(brand_id=None):
    obj = _get_or_404(Brand, brand_id) if brand_id else None
    form = BrandForm(obj=obj)
    if form.validate_on_submit():
        resp = _save_named(Brand, obj, form, "admin.brands", "marca")
        if resp:
            return resp
    return render_template("admin/brands/form.html", form=form, obj=obj)


@bp.route("/marcas/<int:brand_id>/eliminar", methods=["POST"])
def brand_delete(brand_id):
    return _delete_named(Brand, brand_id, "admin.brands", "marca")


# ----------------------------- Descuentos -----------------------------
@bp.route("/descuentos")
def discounts():
    items = Discount.query.order_by(Discount.ends_at.desc()).all()
    return render_template("admin/discounts/list.html", items=items, confirm_form=ConfirmForm())


@bp.route("/descuentos/nuevo", methods=["GET", "POST"])
@bp.route("/descuentos/<int:discount_id>", methods=["GET", "POST"])
def discount_form(discount_id=None):
    obj = _get_or_404(Discount, discount_id) if discount_id else None
    form = DiscountForm(obj=obj)
    form.product_id.choices = [(0, "— Elegir —")] + [
        (p.id, f"{p.sku} · {p.name}") for p in Product.query.order_by(Product.name).all()]
    form.category_id.choices = [(0, "— Elegir —")] + [
        (c.id, c.name) for c in Category.query.order_by(Category.name).all()]
    if obj is not None and not form.is_submitted():
        form.target.data = "product" if obj.product_id else "category"
        form.product_id.data = obj.product_id or 0
        form.category_id.data = obj.category_id or 0

    if form.validate_on_submit():
        if obj is None:
            obj = Discount()
            db.session.add(obj)
        obj.name = form.name.data.strip()
        obj.discount_type = form.discount_type.data
        obj.value = form.value.data
        obj.starts_at = form.starts_at.data
        obj.ends_at = form.ends_at.data
        obj.is_active = form.is_active.data
        if form.target.data == "product":
            obj.product_id, obj.category_id = form.product_id.data, None
        else:
            obj.product_id, obj.category_id = None, form.category_id.data
        db.session.commit()
        flash("Descuento guardado.", "success")
        return redirect(url_for("admin.discounts"))
    return render_template("admin/discounts/form.html", form=form, obj=obj)


@bp.route("/descuentos/<int:discount_id>/eliminar", methods=["POST"])
def discount_delete(discount_id):
    if not ConfirmForm().validate_on_submit():
        abort(400)
    db.session.delete(_get_or_404(Discount, discount_id))
    db.session.commit()
    flash("Descuento eliminado.", "info")
    return redirect(url_for("admin.discounts"))
