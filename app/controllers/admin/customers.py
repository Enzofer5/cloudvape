"""ABM de clientes."""
from flask import abort, current_app, flash, redirect, render_template, request, url_for

from ...forms.admin import ConfirmForm, CustomerForm
from ...models import Order
from ...services import customer_service
from ...services.auth_service import AuthError
from ...utils.helpers import page_arg
from . import bp


def _get_customer(user_id):
    user = customer_service.get_customer(user_id)
    if user is None:
        abort(404)
    return user


@bp.route("/clientes")
def customers():
    q = (request.args.get("q") or "").strip()[:100]
    status = request.args.get("status", "")
    pagination = customer_service.search_customers(q, status, page_arg(),
                                                   current_app.config["ADMIN_ITEMS_PER_PAGE"])
    counts = customer_service.orders_count_map([u.id for u in pagination.items])
    args = request.args.to_dict()
    args.pop("page", None)
    return render_template("admin/customers/list.html", pagination=pagination, counts=counts,
                           q=q, status=status, confirm_form=ConfirmForm(), query_args=args)


@bp.route("/clientes/nuevo", methods=["GET", "POST"])
def customer_new():
    form = CustomerForm()
    if form.validate_on_submit():
        if not form.password.data:
            form.password.errors.append("La contraseña es obligatoria para un cliente nuevo.")
        else:
            try:
                user = customer_service.create_customer(form.data)
            except AuthError as exc:
                form.email.errors.append(str(exc))
            else:
                flash("Cliente creado.", "success")
                return redirect(url_for("admin.customer_detail", user_id=user.id))
    return render_template("admin/customers/form.html", form=form, customer=None)


@bp.route("/clientes/<int:user_id>")
def customer_detail(user_id):
    user = _get_customer(user_id)
    orders = user.orders.order_by(Order.created_at.desc()).all()
    return render_template("admin/customers/detail.html", customer=user, orders=orders)


@bp.route("/clientes/<int:user_id>/editar", methods=["GET", "POST"])
def customer_edit(user_id):
    user = _get_customer(user_id)
    form = CustomerForm(obj=user)
    if request.method == "GET":
        form.is_active.data = user.is_active
    if form.validate_on_submit():
        try:
            customer_service.update_customer(user, form.data)
        except AuthError as exc:
            form.email.errors.append(str(exc))
        else:
            flash("Cliente actualizado.", "success")
            return redirect(url_for("admin.customer_detail", user_id=user.id))
    return render_template("admin/customers/form.html", form=form, customer=user)


@bp.route("/clientes/<int:user_id>/eliminar", methods=["POST"])
def customer_delete(user_id):
    if not ConfirmForm().validate_on_submit():
        abort(400)
    result = customer_service.delete_customer(_get_customer(user_id))
    if result == "deleted":
        flash("Cliente eliminado.", "info")
    else:
        flash("El cliente tiene pedidos: se desactivó la cuenta en lugar de eliminarla.", "warning")
    return redirect(url_for("admin.customers"))
