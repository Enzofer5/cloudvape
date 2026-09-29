"""Formularios del área de cliente y checkout."""
from flask_wtf import FlaskForm
from wtforms import (BooleanField, PasswordField, RadioField, SelectField,
                     StringField, SubmitField, TextAreaField)
from wtforms.validators import DataRequired, EqualTo, Length, Optional, Regexp

from ..models import Order
from .validators import NAME_REGEX, PHONE_REGEX, POSTAL_REGEX, StrongPassword

PROVINCES = [
    "Buenos Aires", "CABA", "Catamarca", "Chaco", "Chubut", "Córdoba", "Corrientes",
    "Entre Ríos", "Formosa", "Jujuy", "La Pampa", "La Rioja", "Mendoza", "Misiones",
    "Neuquén", "Río Negro", "Salta", "San Juan", "San Luis", "Santa Cruz", "Santa Fe",
    "Santiago del Estero", "Tierra del Fuego", "Tucumán",
]
PROVINCE_CHOICES = [(p, p) for p in PROVINCES]


class ProfileForm(FlaskForm):
    first_name = StringField("Nombre", validators=[DataRequired(), Regexp(NAME_REGEX, message="Nombre inválido.")])
    last_name = StringField("Apellido", validators=[DataRequired(), Regexp(NAME_REGEX, message="Apellido inválido.")])
    phone = StringField("Teléfono", validators=[Optional(), Regexp(PHONE_REGEX, message="Teléfono inválido.")])
    submit = SubmitField("Guardar cambios")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Contraseña actual", validators=[DataRequired(), Length(max=128)])
    password = PasswordField("Nueva contraseña", validators=[DataRequired(), StrongPassword(), Length(max=128)])
    confirm = PasswordField("Repetir nueva contraseña", validators=[
        DataRequired(), EqualTo("password", message="Las contraseñas no coinciden.")])
    submit = SubmitField("Cambiar contraseña")


class AddressFieldsMixin:
    street = StringField("Calle", validators=[DataRequired(), Length(max=120)])
    street_number = StringField("Número", validators=[DataRequired(), Length(max=10)])
    apartment = StringField("Piso / Depto", validators=[Optional(), Length(max=20)])
    city = StringField("Ciudad", validators=[DataRequired(), Length(max=80)])
    province = SelectField("Provincia", choices=PROVINCE_CHOICES, validators=[DataRequired()])
    postal_code = StringField("Código postal", validators=[
        DataRequired(), Regexp(POSTAL_REGEX, message="Código postal inválido.")])


class AddressForm(AddressFieldsMixin, FlaskForm):
    label = StringField("Nombre de la dirección", default="Casa", validators=[DataRequired(), Length(max=40)])
    is_default = BooleanField("Usar como dirección principal")
    submit = SubmitField("Guardar dirección")


class CheckoutForm(AddressFieldsMixin, FlaskForm):
    recipient_name = StringField("Nombre de quien recibe", validators=[DataRequired(), Length(max=120)])
    recipient_phone = StringField("Teléfono de contacto", validators=[
        DataRequired(), Regexp(PHONE_REGEX, message="Teléfono inválido.")])
    payment_method = RadioField("Medio de pago", choices=list(Order.PAYMENT_METHODS.items()),
                                default="transfer", validators=[DataRequired()])
    notes = TextAreaField("Notas para el envío (opcional)", validators=[Optional(), Length(max=500)])
    save_address = BooleanField("Guardar esta dirección en mi perfil")
    confirm_age = BooleanField("Confirmo que soy mayor de 18 años y que quien reciba el pedido también lo es",
                               validators=[DataRequired(message="Debés confirmar la mayoría de edad.")])
    submit = SubmitField("Confirmar pedido")
