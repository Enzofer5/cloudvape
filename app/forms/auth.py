"""Formularios de autenticación."""
from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, EmailField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp

from .validators import NAME_REGEX, PHONE_REGEX, MinimumAge, StrongPassword


class RegisterForm(FlaskForm):
    first_name = StringField("Nombre", validators=[
        DataRequired(), Regexp(NAME_REGEX, message="Nombre inválido.")])
    last_name = StringField("Apellido", validators=[
        DataRequired(), Regexp(NAME_REGEX, message="Apellido inválido.")])
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField("Teléfono", validators=[
        Optional(), Regexp(PHONE_REGEX, message="Teléfono inválido.")])
    birth_date = DateField("Fecha de nacimiento", validators=[DataRequired(), MinimumAge()])
    password = PasswordField("Contraseña", validators=[DataRequired(), StrongPassword(), Length(max=128)])
    confirm = PasswordField("Repetir contraseña", validators=[
        DataRequired(), EqualTo("password", message="Las contraseñas no coinciden.")])
    accept_terms = BooleanField("Declaro ser mayor de 18 años y acepto los términos y condiciones",
                                validators=[DataRequired(message="Debés aceptar los términos.")])
    submit = SubmitField("Crear cuenta")


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(max=128)])
    remember = BooleanField("Recordarme")
    submit = SubmitField("Ingresar")


class ForgotPasswordForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField("Enviar enlace")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("Nueva contraseña", validators=[DataRequired(), StrongPassword(), Length(max=128)])
    confirm = PasswordField("Repetir contraseña", validators=[
        DataRequired(), EqualTo("password", message="Las contraseñas no coinciden.")])
    submit = SubmitField("Guardar contraseña")
