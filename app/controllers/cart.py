"""Carrito y checkout."""
from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user

from ..forms.account import CheckoutForm
from ..services import cart_service, order_service
from ..services.cart_service import CartError
from ..services.order_service import OrderError
from ..utils.decorators import customer_required
from ..utils.helpers import format_money

bp = Blueprint("cart", __name__)


def _wants_json() -> bool:
    return request.headers.get("X-Requested-With") == "fetch"


def _int_field(name: str, default: int | None = None) -> int:
    try:
        return int(request.form.get(name, default))
    except (TypeError, ValueError):
        abort(400)


@bp.before_request
def block_admin():
    if current_user.is_authenticated and current_user.is_admin:
        flash("Las cuentas de administrador no pueden comprar. Usá una cuenta de cliente.", "warning")
        return redirect(url_for("admin.dashboard"))


@bp.route("/")
def view():
    summary = cart_service.get_summary()
    for w in summary.warnings:
        flash(w, "warning")
    return render_template("cart/cart.html", cart=summary)


@bp.route("/agregar", methods=["POST"])
def add():
    product_id = _int_field("product_id")
    quantity = _int_field("quantity", 1)
    try:
        cart_service.add(product_id, quantity)
    except CartError as exc:
        if _wants_json():
            return jsonify(ok=False, message=str(exc)), 400
        flash(str(exc), "danger")
        return redirect(request.referrer or url_for("shop.catalog"))
    if _wants_json():
        return jsonify(ok=True, message="Producto agregado al carrito.", count=cart_service.count())
    flash("Producto agregado al carrito.", "success")
    return redirect(url_for("cart.view"))


@bp.route("/actualizar", methods=["POST"])
def update():
    product_id = _int_field("product_id")
    quantity = _int_field("quantity")
    try:
        cart_service.update(product_id, quantity)
    except CartError as exc:
        if _wants_json():
            return jsonify(ok=False, message=str(exc)), 400
        flash(str(exc), "danger")
        return redirect(url_for("cart.view"))
    if _wants_json():
        s = cart_service.get_summary()
        line = next((l for l in s.lines if l.product.id == product_id), None)
        return jsonify(
            ok=True, count=s.count,
            line_total=format_money(line.line_total) if line else None,
            subtotal=format_money(s.subtotal), discount=format_money(s.discount_total),
            shipping=format_money(s.shipping_cost) if s.shipping_cost else "Gratis",
            total=format_money(s.total),
        )
    return redirect(url_for("cart.view"))


@bp.route("/quitar", methods=["POST"])
def remove():
    cart_service.remove(_int_field("product_id"))
    flash("Producto quitado del carrito.", "info")
    return redirect(url_for("cart.view"))


@bp.route("/vaciar", methods=["POST"])
def clear():
    cart_service.clear()
    flash("Vaciaste el carrito.", "info")
    return redirect(url_for("cart.view"))


@bp.route("/checkout", methods=["GET", "POST"])
@customer_required
def checkout():
    summary = cart_service.get_summary()
    if summary.is_empty:
        flash("Tu carrito está vacío.", "warning")
        return redirect(url_for("shop.catalog"))

    form = CheckoutForm()
    addresses = current_user.addresses

    if request.method == "GET":
        form.recipient_name.data = current_user.full_name
        form.recipient_phone.data = current_user.phone
        addr = current_user.default_address
        if addr:
            form.street.data, form.street_number.data = addr.street, addr.street_number
            form.apartment.data, form.city.data = addr.apartment, addr.city
            form.province.data, form.postal_code.data = addr.province, addr.postal_code
        for w in summary.warnings:
            flash(w, "warning")

    if form.validate_on_submit():
        data = {k: getattr(form, k).data for k in (
            "recipient_name", "recipient_phone", "street", "street_number", "apartment", "city",
            "province", "postal_code", "payment_method", "notes", "save_address")}
        try:
            order = order_service.place_order(current_user, data)
        except OrderError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("cart.view"))
        return redirect(url_for("cart.success", order_number=order.order_number))

    return render_template("cart/checkout.html", form=form, cart=summary, addresses=addresses)


@bp.route("/pedido-confirmado/<order_number>")
@customer_required
def success(order_number):
    order = order_service.get_customer_order(current_user, order_number)
    if order is None:
        abort(404)
    return render_template("cart/success.html", order=order)
