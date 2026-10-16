"""Registro, autenticación y recuperación de contraseña."""
import hashlib
import secrets
from datetime import datetime, timedelta

from flask import current_app, render_template, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import PasswordResetToken, Role, User
from ..utils.mailer import send_email


class AuthError(Exception):
    pass


_DUMMY_HASH = generate_password_hash(secrets.token_hex(16))


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def register_customer(first_name, last_name, email, password, birth_date, phone=None) -> User:
    email = normalize_email(email)
    if User.query.filter_by(email=email).first():
        raise AuthError("Ya existe una cuenta con ese email.")
    role = Role.query.filter_by(name=Role.CUSTOMER).one()
    user = User(
        role=role,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email,
        birth_date=birth_date,
        phone=(phone or "").strip() or None,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def authenticate(email: str, password: str) -> User | None:
    user = User.query.filter_by(email=normalize_email(email)).first()
    # Se evalúa el hash aunque el usuario no exista para no revelar qué emails
    # están registrados mediante diferencias de tiempo de respuesta.
    if user is None:
        check_password_hash(_DUMMY_HASH, password)
        return None
    if not user.check_password(password) or not user.is_active:
        return None
    user.last_login_at = datetime.now()
    db.session.commit()
    return user


def change_password(user: User, current_password: str, new_password: str) -> None:
    if not user.check_password(current_password):
        raise AuthError("La contraseña actual no es correcta.")
    user.set_password(new_password)
    db.session.commit()


# ------------------------------------------------------------------
# Recuperación de contraseña
# ------------------------------------------------------------------
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_password_reset(email: str) -> None:
    """Genera un token de un solo uso y envía el enlace por mail.

    Nunca informa si el email existe (evita enumeración de usuarios).
    """
    user = User.query.filter_by(email=normalize_email(email)).first()
    if not user or not user.is_active:
        return

    # Invalida tokens previos no usados
    PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).update(
        {"used_at": datetime.now()}
    )
    token = secrets.token_urlsafe(32)
    minutes = current_app.config["PASSWORD_RESET_EXPIRATION_MINUTES"]
    db.session.add(PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(token),
        expires_at=datetime.now() + timedelta(minutes=minutes),
    ))
    db.session.commit()

    link = url_for("auth.reset_password", token=token, _external=True)
    text = render_template("emails/reset_password.txt", user=user, link=link, minutes=minutes)
    html = render_template("emails/reset_password.html", user=user, link=link, minutes=minutes)
    sent = send_email(user.email, f"{current_app.config['STORE_NAME']} - Recuperar contraseña", text, html)
    if not sent:
        current_app.logger.warning("Enlace de recuperación (modo desarrollo): %s", link)


def get_valid_reset_token(token: str) -> PasswordResetToken | None:
    if not token:
        return None
    prt = PasswordResetToken.query.filter_by(token_hash=_hash_token(token)).first()
    return prt if prt and prt.is_valid else None


def reset_password(token: str, new_password: str) -> None:
    prt = get_valid_reset_token(token)
    if prt is None:
        raise AuthError("El enlace es inválido o expiró. Solicitá uno nuevo.")
    prt.user.set_password(new_password)
    prt.used_at = datetime.now()
    db.session.commit()
