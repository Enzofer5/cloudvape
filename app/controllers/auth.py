"""Registro, login, logout y recuperación de contraseña."""
from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)
from flask_login import current_user, login_required, login_user, logout_user

from ..forms.auth import ForgotPasswordForm, LoginForm, RegisterForm, ResetPasswordForm
from ..services import auth_service, cart_service
from ..services.auth_service import AuthError
from ..utils import rate_limit
from ..utils.helpers import is_safe_redirect

bp = Blueprint("auth", __name__)


def _after_login_redirect(user):
    target = request.args.get("next")
    if is_safe_redirect(target):
        return redirect(target)
    return redirect(url_for("admin.dashboard") if user.is_admin else url_for("shop.index"))


def _start_session(user, remember=False):
    # Se preserva el carrito de invitado y se regenera la sesión (evita session fixation)
    guest_cart = session.get(cart_service.SESSION_KEY)
    session.clear()
    if guest_cart:
        session[cart_service.SESSION_KEY] = guest_cart
    login_user(user, remember=remember)
    session.permanent = True
    cart_service.merge_session_cart_into_user(user)


@bp.route("/registro", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("shop.index"))
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            user = auth_service.register_customer(
                form.first_name.data, form.last_name.data, form.email.data,
                form.password.data, form.birth_date.data, form.phone.data,
            )
        except AuthError as exc:
            form.email.errors.append(str(exc))
        else:
            _start_session(user)
            flash("¡Bienvenido/a! Tu cuenta fue creada.", "success")
            return redirect(url_for("shop.index"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("shop.index"))
    form = LoginForm()
    if form.validate_on_submit():
        key = f"{request.remote_addr}|{form.email.data.strip().lower()}"
        if rate_limit.is_blocked(key):
            flash("Demasiados intentos fallidos. Esperá 15 minutos e intentá de nuevo.", "danger")
            return render_template("auth/login.html", form=form), 429
        user = auth_service.authenticate(form.email.data, form.password.data)
        if user is None:
            rate_limit.register_failure(key)
            flash("Email o contraseña incorrectos.", "danger")
        else:
            rate_limit.reset(key)
            _start_session(user, remember=form.remember.data)
            flash(f"Hola, {user.first_name}.", "success")
            return _after_login_redirect(user)
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("Cerraste sesión.", "info")
    return redirect(url_for("shop.index"))


@bp.route("/recuperar", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        auth_service.request_password_reset(form.email.data)
        # Mismo mensaje exista o no el email (evita enumeración de cuentas)
        flash("Si el email está registrado, te enviamos un enlace para restablecer la contraseña.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@bp.route("/restablecer/<token>", methods=["GET", "POST"])
def reset_password(token):
    if auth_service.get_valid_reset_token(token) is None:
        flash("El enlace es inválido o expiró. Solicitá uno nuevo.", "danger")
        return redirect(url_for("auth.forgot_password"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        try:
            auth_service.reset_password(token, form.password.data)
        except AuthError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("auth.forgot_password"))
        flash("Tu contraseña fue actualizada. Ya podés iniciar sesión.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)
