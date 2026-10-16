"""Validadores reutilizables."""
import re
from datetime import date

from flask import current_app
from wtforms.validators import ValidationError


class StrongPassword:
    """Mínimo 8 caracteres, al menos una letra y un número."""

    def __init__(self, message=None):
        self.message = message or "La contraseña debe tener al menos 8 caracteres, una letra y un número."

    def __call__(self, form, field):
        pwd = field.data or ""
        if len(pwd) < 8 or not re.search(r"[A-Za-z]", pwd) or not re.search(r"\d", pwd):
            raise ValidationError(self.message)


class MinimumAge:
    """Verifica mayoría de edad (venta de productos de vapeo)."""

    def __call__(self, form, field):
        if not field.data:
            return
        min_age = current_app.config.get("MIN_CUSTOMER_AGE", 18)
        today = date.today()
        b = field.data
        age = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
        if b > today or age > 120:
            raise ValidationError("Fecha de nacimiento inválida.")
        if age < min_age:
            raise ValidationError(f"Tenés que ser mayor de {min_age} años para comprar en esta tienda.")


PHONE_REGEX = r"^[0-9+()\-\s]{6,30}$"
NAME_REGEX = r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' \-]{2,60}$"
POSTAL_REGEX = r"^[A-Za-z0-9 ]{3,10}$"
