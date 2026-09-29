"""Área del cliente: perfil, contraseña, direcciones e historial de pedidos."""
from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user

from ..extensions import db
from ..forms.account import AddressForm, ChangePasswordForm, ProfileForm
from ..forms.admin import ConfirmForm
from ..models import Address
from ..services import auth_service, order_service
from ..services.auth_service import AuthError
from ..services.order_service import OrderError
from ..utils.decorators import customer_required
from ..utils.helpers import page_arg

bp = Blueprint("account", __name__)


@bp.before_request
@customer_required
def protect():
    """Todas las rutas de este blueprint requieren un cliente logueado."""
    return None


@bp.route("/", methods=["GET", "POST"])
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.first_name = form.first_name.data.strip()
        current_user.last_name = form.last_name.data.strip()
        current_user.phone = (form.phone.data or "").strip() or None
        db.session.commit()
        flash("Datos actualizados.", "success")
        return redirect(url_for("account.profile"))
    recent = order_service.customer_orders(current_user, 1, 3).items
    return render_template("account/profile.html", form=form, recent_orders=recent)


@bp.route("/contrasena", methods=["GET", "POST"])
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        try:
            auth_service.change_password(current_user, form.current_password.data, form.password.data)
        except AuthError as exc:
            form.current_password.errors.append(str(exc))
        else:
            flash("Contraseña actualizada.", "success")
            return redirect(url_for("account.profile"))
    return render_template("account/password.html", form=form)


# ---------------------------- Direcciones ----------------------------
def _own_address(address_id: int) -> Address:
    addr = db.session.get(Address, address_id)
    if addr is None or addr.user_id != current_user.id:
        abort(404)
    return addr


def _set_default(addr: Address) -> None:
    for a in current_user.addresses:
        a.is_default = a.id == addr.id


@bp.route("/direcciones")
def addresses():
    return render_template("account/addresses.html", addresses=current_user.addresses, confirm_form=ConfirmForm())


@bp.route("/direcciones/nueva", methods=["GET", "POST"])
@bp.route("/direcciones/<int:address_id>/editar", methods=["GET", "POST"])
def address_form(address_id=None):
    addr = _own_address(address_id) if address_id else None
    form = AddressForm(obj=addr)
    if form.validate_on_submit():
        if addr is None:
            addr = Address()
            current_user.addresses.append(addr)
        form.populate_obj(addr)
        db.session.flush()
        if form.is_default.data or len(current_user.addresses) == 1:
            _set_default(addr)
        db.session.commit()
        flash("Dirección guardada.", "success")
        return redirect(url_for("account.addresses"))
    return render_template("account/address_form.html", form=form, address=addr)


@bp.route("/direcciones/<int:address_id>/eliminar", methods=["POST"])
def address_delete(address_id):
    if not ConfirmForm().validate_on_submit():
        abort(400)
    addr = _own_address(address_id)
    was_default = addr.is_default
    current_user.addresses.remove(addr)  # delete-orphan elimina la fila
    db.session.flush()
    if was_default and current_user.addresses:
        current_user.addresses[0].is_default = True
    db.session.commit()
    flash("Dirección eliminada.", "info")
    return redirect(url_for("account.addresses"))


@bp.route("/direcciones/<int:address_id>/principal", methods=["POST"])
def address_default(address_id):
    if not ConfirmForm().validate_on_submit():
        abort(400)
    _set_default(_own_address(address_id))
    db.session.commit()
    flash("Dirección principal actualizada.", "success")
    return redirect(url_for("account.addresses"))


# ------------------------------ Pedidos ------------------------------
@bp.route("/pedidos")
def orders():
    pagination = order_service.customer_orders(current_user, page_arg())
    return render_template("account/orders.html", pagination=pagination)


@bp.route("/pedidos/<order_number>")
def order_detail(order_number):
    order = order_service.get_customer_order(current_user, order_number)
    if order is None:
        abort(404)
    return render_template("account/order_detail.html", order=order,
                           statuses=order_service.all_statuses(), confirm_form=ConfirmForm())


@bp.route("/pedidos/<order_number>/cancelar", methods=["POST"])
def order_cancel(order_number):
    if not ConfirmForm().validate_on_submit():
        abort(400)
    order = order_service.get_customer_order(current_user, order_number)
    if order is None:
        abort(404)
    try:
        order_service.cancel_by_customer(order, current_user)
        flash("Pedido cancelado.", "info")
    except OrderError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("account.order_detail", order_number=order_number))
