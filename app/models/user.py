"""Modelos de usuarios, roles, direcciones y tokens de recuperación."""
from datetime import date, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class Role(db.Model):
    __tablename__ = "roles"

    ADMIN = "admin"
    CUSTOMER = "customer"

    id = db.Column(db.SmallInteger, primary_key=True)
    name = db.Column(db.String(30), nullable=False, unique=True)
    description = db.Column(db.String(120))

    users = db.relationship("User", back_populates="role", lazy="dynamic")

    def __repr__(self):
        return f"<Role {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.SmallInteger, db.ForeignKey("roles.id"), nullable=False)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30))
    birth_date = db.Column(db.Date, nullable=False)
    is_active_flag = db.Column("is_active", db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    role = db.relationship("Role", back_populates="users")
    addresses = db.relationship(
        "Address", back_populates="user", cascade="all, delete-orphan",
        order_by="Address.is_default.desc()",
    )
    orders = db.relationship("Order", back_populates="user", lazy="dynamic")
    cart_items = db.relationship("CartItem", back_populates="user", cascade="all, delete-orphan")

    # --- Contraseñas: solo se almacena el hash (scrypt/pbkdf2 de Werkzeug) ---
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    # --- Flask-Login ---
    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return bool(self.is_active_flag)

    @property
    def is_admin(self) -> bool:
        return self.role is not None and self.role.name == Role.ADMIN

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int:
        today = date.today()
        b = self.birth_date
        return today.year - b.year - ((today.month, today.day) < (b.month, b.day))

    @property
    def default_address(self):
        for a in self.addresses:
            if a.is_default:
                return a
        return self.addresses[0] if self.addresses else None

    def __repr__(self):
        return f"<User {self.email}>"


class Address(db.Model):
    __tablename__ = "addresses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    label = db.Column(db.String(40), nullable=False, default="Casa")
    street = db.Column(db.String(120), nullable=False)
    street_number = db.Column(db.String(10), nullable=False)
    apartment = db.Column(db.String(20))
    city = db.Column(db.String(80), nullable=False)
    province = db.Column(db.String(80), nullable=False)
    postal_code = db.Column(db.String(10), nullable=False)
    is_default = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", back_populates="addresses")

    @property
    def one_line(self) -> str:
        apt = f" {self.apartment}" if self.apartment else ""
        return (f"{self.street} {self.street_number}{apt}, {self.city}, "
                f"{self.province} ({self.postal_code})")


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    user = db.relationship("User")

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > datetime.now()
