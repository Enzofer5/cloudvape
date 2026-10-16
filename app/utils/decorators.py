"""Decoradores de control de acceso por rol."""
from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def admin_required(view):
    """Permite el acceso solo a usuarios autenticados con rol administrador."""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def customer_required(view):
    """Rutas exclusivas de clientes (el admin no compra con su cuenta)."""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped
