"""Formularios del panel de administración."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, MultipleFileField
from wtforms import (BooleanField, DateField, DateTimeLocalField, DecimalField,
                     EmailField, IntegerField, PasswordField, SelectField,
                     StringField, SubmitField, TextAreaField)
from wtforms.validators import (DataRequired, Email, Length, NumberRange,
                                Optional, Regexp, ValidationError)

from .validators import NAME_REGEX, PHONE_REGEX, MinimumAge, StrongPassword

IMAGE_EXTS = ["jpg", "jpeg", "png", "webp"]


class ProductForm(FlaskForm):
    name = StringField("Nombre", validators=[DataRequired(), Length(max=150)])
    sku = StringField("SKU", validators=[
        DataRequired(), Length(max=40),
        Regexp(r"^[A-Za-z0-9\-_]+$", message="Solo letras, números, guiones y guión bajo.")])
    category_id = SelectField("Categoría", coerce=int, validators=[DataRequired()])
    brand_id = SelectField("Marca", coerce=int, validators=[DataRequired()])
    price = DecimalField("Precio de lista ($)", places=2, validators=[DataRequired(), NumberRange(min=0)])
    stock = IntegerField("Stock inicial", default=0, validators=[Optional(), NumberRange(min=0, max=100000)])
    min_stock = IntegerField("Stock mínimo (alerta)", default=5, validators=[NumberRange(min=0, max=10000)])
    short_description = StringField("Descripción corta", validators=[Optional(), Length(max=255)])
    description = TextAreaField("Descripción completa", validators=[Optional(), Length(max=10000)])
    nicotine_mg = DecimalField("Nicotina (mg/ml)", places=2, validators=[Optional(), NumberRange(min=0, max=100)])
    volume_ml = DecimalField("Volumen (ml)", places=2, validators=[Optional(), NumberRange(min=0, max=1000)])
    puffs = IntegerField("Puffs / caladas", validators=[Optional(), NumberRange(min=0, max=100000)])
    flavor = StringField("Sabor", validators=[Optional(), Length(max=80)])
    is_active = BooleanField("Publicado", default=True)
    is_featured = BooleanField("Destacado en portada")
    images = MultipleFileField("Imágenes", validators=[FileAllowed(IMAGE_EXTS, "Solo imágenes JPG, PNG o WEBP.")])
    submit = SubmitField("Guardar producto")


class CategoryForm(FlaskForm):
    name = StringField("Nombre", validators=[DataRequired(), Length(max=80)])
    description = StringField("Descripción", validators=[Optional(), Length(max=255)])
    is_active = BooleanField("Activa", default=True)
    submit = SubmitField("Guardar")


class BrandForm(FlaskForm):
    name = StringField("Nombre", validators=[DataRequired(), Length(max=80)])
    is_active = BooleanField("Activa", default=True)
    submit = SubmitField("Guardar")


class DiscountForm(FlaskForm):
    name = StringField("Nombre de la promoción", validators=[DataRequired(), Length(max=100)])
    discount_type = SelectField("Tipo", choices=[("percent", "Porcentaje (%)"), ("fixed", "Monto fijo ($)")])
    value = DecimalField("Valor", places=2, validators=[DataRequired(), NumberRange(min=0.01)])
    target = SelectField("Aplicar a", choices=[("product", "Un producto"), ("category", "Una categoría")])
    product_id = SelectField("Producto", coerce=int, validators=[Optional()])
    category_id = SelectField("Categoría", coerce=int, validators=[Optional()])
    starts_at = DateTimeLocalField("Desde", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    ends_at = DateTimeLocalField("Hasta", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    is_active = BooleanField("Activo", default=True)
    submit = SubmitField("Guardar descuento")

    def validate_value(self, field):
        if self.discount_type.data == "percent" and field.data and field.data > 100:
            raise ValidationError("Un porcentaje no puede superar 100.")

    def validate_ends_at(self, field):
        if self.starts_at.data and field.data and field.data <= self.starts_at.data:
            raise ValidationError("La fecha de fin debe ser posterior al inicio.")

    def validate_product_id(self, field):
        if self.target.data == "product" and not field.data:
            raise ValidationError("Elegí un producto.")

    def validate_category_id(self, field):
        if self.target.data == "category" and not field.data:
            raise ValidationError("Elegí una categoría.")


class StockAdjustForm(FlaskForm):
    change_qty = IntegerField("Cantidad (+ entrada / − salida)", validators=[
        DataRequired(), NumberRange(min=-100000, max=100000)])
    reason = SelectField("Motivo", choices=[("purchase", "Compra a proveedor"), ("adjustment", "Ajuste manual")])
    note = StringField("Nota", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Registrar movimiento")


class BulkPriceForm(FlaskForm):
    percent = DecimalField("Variación (%)", places=2, validators=[
        DataRequired(), NumberRange(min=-99, max=500)])
    category_id = SelectField("Categoría", coerce=int, validators=[Optional()])
    brand_id = SelectField("Marca", coerce=int, validators=[Optional()])
    submit = SubmitField("Aplicar actualización")


class CustomerForm(FlaskForm):
    first_name = StringField("Nombre", validators=[DataRequired(), Regexp(NAME_REGEX, message="Nombre inválido.")])
    last_name = StringField("Apellido", validators=[DataRequired(), Regexp(NAME_REGEX, message="Apellido inválido.")])
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField("Teléfono", validators=[Optional(), Regexp(PHONE_REGEX, message="Teléfono inválido.")])
    birth_date = DateField("Fecha de nacimiento", validators=[DataRequired(), MinimumAge()])
    password = PasswordField("Contraseña", validators=[Optional(), StrongPassword(), Length(max=128)])
    is_active = BooleanField("Cuenta activa", default=True)
    submit = SubmitField("Guardar cliente")


class OrderStatusForm(FlaskForm):
    status = SelectField("Nuevo estado", validators=[DataRequired()])
    comment = StringField("Comentario (opcional)", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Actualizar estado")


class ConfirmForm(FlaskForm):
    """Formulario vacío: solo aporta el token CSRF para acciones POST (borrar, etc.)."""
    submit = SubmitField("Confirmar")
