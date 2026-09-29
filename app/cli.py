"""Comandos de consola:  flask init-db | flask create-admin | flask seed-demo"""
import os
import random
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import click
from flask import current_app
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import text

from .extensions import db
from .models import (Brand, Category, Order, OrderItem, OrderStatus,
                     OrderStatusHistory, Product, ProductImage, Role,
                     StockMovement, User)
from .utils.helpers import slugify


def register_cli(app):
    app.cli.add_command(init_db)
    app.cli.add_command(create_admin)
    app.cli.add_command(seed_demo)


def _split_sql(script: str):
    """Divide el script en sentencias (el schema no contiene ';' dentro de literales)."""
    lines = [l for l in script.splitlines() if not l.strip().startswith("--")]
    for stmt in "\n".join(lines).split(";"):
        if stmt.strip():
            yield stmt.strip()


@click.command("init-db")
@click.option("--yes", is_flag=True, help="No pedir confirmación.")
def init_db(yes):
    """Crea (o RECREA) todas las tablas ejecutando database/schema.sql."""
    if not yes:
        click.confirm("Esto BORRA y recrea todas las tablas. ¿Continuar?", abort=True)
    if db.engine.dialect.name == "sqlite":
        _init_sqlite()
        click.echo("Base de datos de demostración (SQLite) inicializada.")
        return
    path = os.path.join(current_app.root_path, "..", "database", "schema.sql")
    with open(path, encoding="utf-8") as fh:
        script = fh.read()
    with db.engine.begin() as conn:
        for stmt in _split_sql(script):
            conn.execute(text(stmt))
    click.echo("Base de datos inicializada correctamente.")


def _init_sqlite():
    """Modo demo: crea las tablas desde los modelos (sin necesidad de MySQL)."""
    db.drop_all()
    db.create_all()
    db.session.add_all([
        Role(id=1, name=Role.ADMIN, description="Administrador de la tienda"),
        Role(id=2, name=Role.CUSTOMER, description="Cliente"),
    ])
    for i, (code, name) in enumerate([
        ("pending", "Pendiente de pago"), ("paid", "Pagado"), ("preparing", "En preparación"),
        ("shipped", "Enviado"), ("delivered", "Entregado"), ("cancelled", "Cancelado"),
    ], start=1):
        db.session.add(OrderStatus(id=i, code=code, name=name, sort_order=i))
    db.session.commit()


@click.command("create-admin")
@click.option("--email", prompt="Email del administrador")
@click.option("--first-name", prompt="Nombre", default="Admin")
@click.option("--last-name", prompt="Apellido", default="Tienda")
@click.password_option("--password", prompt="Contraseña", confirmation_prompt=True)
def create_admin(email, first_name, last_name, password):
    """Crea un usuario administrador."""
    email = email.strip().lower()
    if len(password) < 8:
        raise click.ClickException("La contraseña debe tener al menos 8 caracteres.")
    if User.query.filter_by(email=email).first():
        raise click.ClickException("Ya existe un usuario con ese email.")
    admin = User(role=Role.query.filter_by(name=Role.ADMIN).one(), first_name=first_name,
                 last_name=last_name, email=email, birth_date=date(1990, 1, 1))
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    click.echo(f"Administrador {email} creado.")


# ----------------------------------------------------------------------
# Datos de demostración
# ----------------------------------------------------------------------
DEMO_CATEGORIES = [
    ("Vapes descartables", "Listos para usar, sin recarga ni mantenimiento."),
    ("Pods recargables", "Sistemas compactos con cartuchos recargables."),
    ("Líquidos", "E-liquids de sales de nicotina y freebase."),
    ("Resistencias y cartuchos", "Repuestos para tu equipo."),
    ("Accesorios", "Cargadores, fundas y más."),
]
DEMO_BRANDS = ["Elf Bar", "Lost Mary", "Vaporesso", "Uwell", "Geek Vape", "Nasty Juice"]
FLAVORS = ["Frutilla Kiwi", "Mango Helado", "Uva", "Sandía", "Menta", "Blueberry",
           "Tabaco Clásico", "Frutos Rojos", "Durazno", "Limonada Rosa", "Maracuyá", "Cola"]
PALETTE = [("#1a1a1a", "#4d4d4d"), ("#2b2b2b", "#b3b3b3"), ("#0d0d0d", "#6e6e6e"),
           ("#3a3a3a", "#9a9a9a"), ("#111111", "#5c5c5c"), ("#262626", "#838383")]


def _load_font(bold: bool, size: int):
    names = (["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "segoeuib.ttf"] if bold
             else ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "segoeui.ttf"])
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _placeholder_image(title: str, subtitle: str, colors) -> str:
    w, h = 800, 800
    img = Image.new("RGB", (w, h), colors[0])
    top, bottom = Image.new("RGB", (1, 1), colors[0]).getpixel((0, 0)), Image.new("RGB", (1, 1), colors[1]).getpixel((0, 0))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    # silueta simple de un vape
    draw.rounded_rectangle([330, 150, 470, 600], radius=50, fill=(255, 255, 255, 60), outline="white", width=6)
    draw.rounded_rectangle([370, 90, 430, 160], radius=20, fill="white")
    font, small = _load_font(True, 44), _load_font(False, 32)
    for text_value, y, f in ((title[:28], 670, font), (subtitle[:34], 725, small)):
        try:
            draw.text((w / 2, y), text_value, fill="white", font=f, anchor="mm")
        except (ValueError, TypeError):  # fuente bitmap sin soporte de anchor
            draw.text((w / 2 - len(text_value) * 4, y), text_value, fill="white", font=f)
    filename = f"{uuid.uuid4().hex}.webp"
    img.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename), "WEBP", quality=80)
    return filename


@click.command("seed-demo")
@click.option("--orders", default=60, help="Cantidad de pedidos de ejemplo.")
def seed_demo(orders):
    """Carga categorías, marcas, productos, un cliente demo y pedidos de ejemplo."""
    if Product.query.first():
        raise click.ClickException("Ya hay productos cargados. Ejecutá 'flask init-db' para empezar de cero.")
    random.seed(42)

    cats = []
    for name, desc in DEMO_CATEGORIES:
        c = Category(name=name, slug=slugify(name), description=desc)
        db.session.add(c)
        cats.append(c)
    brands = []
    for name in DEMO_BRANDS:
        b = Brand(name=name, slug=slugify(name))
        db.session.add(b)
        brands.append(b)
    db.session.flush()

    products = []
    n = 1
    for cat_idx, cat in enumerate(cats):
        for i in range(6):
            brand = brands[(cat_idx + i) % len(brands)]
            flavor = FLAVORS[(cat_idx * 3 + i) % len(FLAVORS)]
            if cat_idx == 0:
                puffs = random.choice([5000, 8000, 12000, 20000])
                name, price, nic, vol = f"{brand.name} {puffs // 1000}K {flavor}", random.choice([14900, 18900, 24900, 29900]), 50, None
            elif cat_idx == 1:
                puffs, name, price, nic, vol = None, f"{brand.name} Pod Kit {['Go', 'Pro', 'Mini', 'X', 'Nano', 'Lite'][i]}", random.choice([39900, 54900, 69900]), None, 2
            elif cat_idx == 2:
                puffs, name, price, nic, vol = None, f"{brand.name} Salt {flavor} 30ml", random.choice([9900, 12900, 15900]), random.choice([0, 20, 35, 50]), 30
            elif cat_idx == 3:
                puffs, name, price, nic, vol = None, f"{brand.name} Cartucho x{random.choice([2, 3, 4])} {['0.6Ω', '0.8Ω', '1.0Ω', '1.2Ω', '0.4Ω', '0.7Ω'][i]}", random.choice([6900, 8900, 11900]), None, None
            else:
                puffs, name, price, nic, vol = None, ["Cargador USB-C rápido", "Funda de silicona", "Cordón porta vape", "Estuche rígido", "Kit limpieza", "Batería externa 5000mAh"][i], random.choice([3900, 5900, 8900]), None, None
            stock = random.choice([0, 3, 12, 25, 40, 60])
            p = Product(
                category=cat, brand=brand, sku=f"CV-{n:04d}", name=name, slug=slugify(f"{name}-{n}"),
                short_description=f"{cat.name[:-1] if cat.name.endswith('s') else cat.name} {brand.name}" +
                                  (f" sabor {flavor}." if cat_idx in (0, 2) else "."),
                description=(f"{name}.\n\nProducto original {brand.name}. Ideal para quienes buscan calidad "
                             f"y rendimiento. Venta exclusiva a mayores de 18 años.\n\n"
                             f"Advertencia: contiene nicotina, sustancia altamente adictiva." if nic else
                             f"{name}.\n\nProducto original {brand.name}. Venta exclusiva a mayores de 18 años."),
                price=Decimal(price), stock=stock, min_stock=5,
                nicotine_mg=Decimal(nic) if nic is not None else None,
                volume_ml=Decimal(vol) if vol else None, puffs=puffs,
                flavor=flavor if cat_idx in (0, 2) else None,
                is_featured=(i < 2),
            )
            colors = PALETTE[(cat_idx + i) % len(PALETTE)]
            p.images.append(ProductImage(filename=_placeholder_image(brand.name, flavor if cat_idx in (0, 2) else cat.name, colors), is_main=True))
            p.images.append(ProductImage(filename=_placeholder_image(name.split()[0], current_app.config["STORE_NAME"], colors[::-1]), sort_order=1))
            db.session.add(p)
            products.append(p)
            n += 1
    db.session.flush()
    for p in products:
        if p.stock:
            db.session.add(StockMovement(product_id=p.id, change_qty=p.stock, reason="initial"))

    # Descuento de ejemplo en líquidos
    from .models import Discount
    db.session.add(Discount(name="Semana del líquido", discount_type="percent", value=Decimal("15"),
                            category=cats[2], starts_at=datetime.now() - timedelta(days=1),
                            ends_at=datetime.now() + timedelta(days=30)))

    customer_role = Role.query.filter_by(name=Role.CUSTOMER).one()
    customers = []
    for i, (fn, ln) in enumerate([("Juan", "Pérez"), ("María", "Gómez"), ("Lucas", "Fernández"),
                                  ("Sofía", "López"), ("Martín", "Díaz")]):
        u = User(role=customer_role, first_name=fn, last_name=ln,
                 email="cliente@demo.com" if i == 0 else f"{slugify(fn)}.{slugify(ln)}@demo.com",
                 birth_date=date(1990 + i, 5, 10), phone="11 5555-000" + str(i),
                 created_at=datetime.now() - timedelta(days=random.randint(1, 90)))
        u.set_password("Demo1234")
        db.session.add(u)
        customers.append(u)
    db.session.flush()

    statuses = {s.code: s for s in OrderStatus.query.all()}
    weights = [("delivered", 45), ("shipped", 10), ("preparing", 8), ("paid", 12), ("pending", 10), ("cancelled", 15)]
    sellable = [p for p in products if p.stock > 0]
    for k in range(orders):
        u = random.choice(customers)
        created = datetime.now() - timedelta(days=random.randint(0, 59), hours=random.randint(0, 23))
        code = random.choices([w[0] for w in weights], [w[1] for w in weights])[0]
        o = Order(order_number=f"CV-{created:%y%m%d}-{k:04X}", user=u, status=statuses[code],
                  payment_method=random.choice(list(Order.PAYMENT_METHODS)), shipping_cost=Decimal("3500"),
                  recipient_name=u.full_name, recipient_phone=u.phone, ship_street="Av. Corrientes",
                  ship_number=str(random.randint(100, 5000)), ship_city="Buenos Aires", ship_province="CABA",
                  ship_postal_code="C1043", created_at=created, updated_at=created)
        for p in random.sample(sellable, random.randint(1, 3)):
            price = Decimal(p.price)
            unit = (price * Decimal("0.85")).quantize(Decimal("0.01")) if p.category_id == cats[2].id else price
            o.items.append(OrderItem(product_id=p.id, product_name=p.name, list_price=price,
                                     unit_price=unit, quantity=random.randint(1, 3)))
        o.history.append(OrderStatusHistory(status=statuses["pending"], changed_by=u.id,
                                            comment="Pedido creado por el cliente", created_at=created))
        if code != "pending":
            o.history.append(OrderStatusHistory(status=statuses[code], created_at=created + timedelta(hours=6)))
        db.session.add(o)
    db.session.commit()
    click.echo(f"Datos demo cargados: {len(products)} productos, {len(customers)} clientes, {orders} pedidos.")
    click.echo("Cliente demo: cliente@demo.com / Demo1234")
