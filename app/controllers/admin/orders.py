"""Gestión de pedidos y cambios de estado."""
from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload

from ...extensions import db
from ...forms.admin import OrderStatusForm
from ...models import Order, OrderStatus, User
from ...services import order_service
from ...services.catalog_service import _escape_like
from ...services.order_service import OrderError
from ...utils.helpers import day_end, day_start, page_arg, parse_date
from . import bp


@bp.route("/pedidos")
def orders():
    q = (request.args.get("q") or "").strip()[:100]
    status = request.args.get("status", "")
    date_from = parse_date(request.args.get("from"))
    date_to = parse_date(request.args.get("to"))

    query = (Order.query.join(User, User.id == Order.user_id)
             .join(OrderStatus, OrderStatus.id == Order.status_id)
             .options(selectinload(Order.items), joinedload(Order.user), joinedload(Order.status)))
    if q:
        like = f"%{_escape_like(q)}%"
        query = query.filter(or_(Order.order_number.ilike(like, escape="\\"),
                                 User.email.ilike(like, escape="\\"),
                                 User.last_name.ilike(like, escape="\\"),
                                 Order.recipient_name.ilike(like, escape="\\")))
    if status:
        query = query.filter(OrderStatus.code == status)
    if date_from:
        query = query.filter(Order.created_at >= day_start(date_from))
    if date_to:
        query = query.filter(Order.created_at <= day_end(date_to))

    pagination = db.paginate(query.order_by(Order.created_at.desc()), page=page_arg(),
                             per_page=current_app.config["ADMIN_ITEMS_PER_PAGE"], error_out=False)
    args = request.args.to_dict()
    args.pop("page", None)
    return render_template("admin/orders/list.html", pagination=pagination, statuses=order_service.all_statuses(),
                           q=q, status=status, date_from=date_from, date_to=date_to, query_args=args)


@bp.route("/pedidos/<int:order_id>", methods=["GET", "POST"])
def order_detail(order_id):
    order = db.session.get(Order, order_id)
    if order is None:
        abort(404)
    form = OrderStatusForm()
    allowed = [s for s in order_service.all_statuses() if order.status.can_transition_to(s.code)]
    form.status.choices = [(s.code, s.name) for s in allowed]

    if allowed and form.validate_on_submit():
        try:
            order_service.change_status(order, form.status.data, current_user, form.comment.data)
        except OrderError as exc:
            flash(str(exc), "danger")
        else:
            flash(f"Estado actualizado a '{order.status.name}'.", "success")
        return redirect(url_for("admin.order_detail", order_id=order.id))
    return render_template("admin/orders/detail.html", order=order, form=form, allowed=allowed)
