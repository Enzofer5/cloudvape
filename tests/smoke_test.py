"""Prueba de humo end-to-end sobre la base configurada en .env (requiere datos demo)."""
import os
import re
import sys

sys.path.insert(0, ".")
from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Order, Product  # noqa: E402

ADMIN_EMAIL = os.getenv("SMOKE_ADMIN_EMAIL", "admin@demo.com")  # admin con clave Admin1234
app = create_app("development")
app.config["WTF_CSRF_ENABLED"] = False
app.config["DEBUG"] = False
app.config["PROPAGATE_EXCEPTIONS"] = True
c = app.test_client()

def ok(resp, code=200, msg=""):
    assert resp.status_code == code, f"{msg} -> {resp.status_code}\n{resp.get_data(as_text=True)[:800]}"
    return resp

# Públicas
for url in ["/", "/productos", "/productos?q=mango", "/productos?category=liquidos&sort=price_asc&in_stock=1&brand=1&brand=2&min_price=1000&max_price=99999&nicotine=high",
            "/terminos", "/carrito/", "/auth/login", "/auth/registro", "/auth/recuperar"]:
    ok(c.get(url), msg=url)
ok(c.get("/no-existe"), 404)
with app.app_context():
    p = Product.query.filter(Product.stock > 3, Product.is_active.is_(True)).first()
    pid, slug = p.id, p.slug
ok(c.get(f"/producto/{slug}"))
# Rutas protegidas
assert c.get("/admin/").status_code == 302
assert c.get("/mi-cuenta/").status_code == 302
# Carrito como invitado + AJAX
r = ok(c.post("/carrito/agregar", data={"product_id": pid, "quantity": 2}, headers={"X-Requested-With": "fetch"}))
assert r.json["count"] == 2, r.json
r = c.post("/carrito/agregar", data={"product_id": pid, "quantity": 999}, headers={"X-Requested-With": "fetch"})
assert r.status_code == 400
# Registro menor de edad
r = ok(c.post("/auth/registro", data=dict(first_name="Nene", last_name="Test", email="nene@test.com", birth_date="2015-01-01",
                                        password="Clave1234", confirm="Clave1234", accept_terms="y")))
assert "mayor de 18" in r.get_data(as_text=True)
# Registro válido (merge carrito)
r = c.post("/auth/registro", data=dict(first_name="Ana", last_name="Test", email="ana@test.com", birth_date="1995-01-01",
                                       password="Clave1234", confirm="Clave1234", accept_terms="y"))
assert r.status_code == 302, r.get_data(as_text=True)[:500]
r = ok(c.get("/carrito/")); assert "Finalizar compra" in r.get_data(as_text=True)
r = ok(c.post("/carrito/actualizar", data={"product_id": pid, "quantity": 3}, headers={"X-Requested-With": "fetch"}))
assert r.json["count"] == 3
ok(c.get("/carrito/checkout"))
with app.app_context():
    stock_before = db.session.get(Product, pid).stock
r = c.post("/carrito/checkout", data=dict(recipient_name="Ana Test", recipient_phone="11 4444-5555", street="Florida", street_number="100",
        city="CABA", province="CABA", postal_code="C1005", payment_method="transfer", save_address="y", confirm_age="y"))
assert r.status_code == 302, r.get_data(as_text=True)[:1500]
num = r.headers["Location"].rsplit("/", 1)[-1]
ok(c.get(r.headers["Location"]))
with app.app_context():
    assert db.session.get(Product, pid).stock == stock_before - 3
ok(c.get("/mi-cuenta/")); ok(c.get("/mi-cuenta/pedidos")); ok(c.get(f"/mi-cuenta/pedidos/{num}"))
ok(c.get("/mi-cuenta/direcciones")); ok(c.get("/mi-cuenta/direcciones/nueva")); ok(c.get("/mi-cuenta/contrasena"))
r = c.post("/mi-cuenta/direcciones/nueva", data=dict(label="Trabajo", street="Lavalle", street_number="200", city="CABA", province="CABA", postal_code="C1047"))
assert r.status_code == 302
# Cancelación por el cliente devuelve stock
assert c.post(f"/mi-cuenta/pedidos/{num}/cancelar").status_code == 302
with app.app_context():
    assert db.session.get(Product, pid).stock == stock_before
    assert Order.query.filter_by(order_number=num).one().status.code == "cancelled"
# Cliente no puede entrar al admin
assert c.get("/admin/").status_code == 403
ok(c.post("/auth/logout"), 302)

# Recuperación de contraseña (captura del link en el log)
import logging
records = []
class H(logging.Handler):
    def emit(self, rec): records.append(rec.getMessage())
app.logger.addHandler(H())
ok(c.post("/auth/recuperar", data={"email": "ana@test.com"}), 302)
link = next(m for m in records if "restablecer" in m)
token_path = re.search(r"(/auth/restablecer/[\w\-]+)", link).group(1)
ok(c.get(token_path))
assert c.post(token_path, data={"password": "Nueva1234", "confirm": "Nueva1234"}).status_code == 302
assert c.get(token_path).status_code == 302  # token de un solo uso
r = c.post("/auth/login", data={"email": "ana@test.com", "password": "Nueva1234"}); assert r.status_code == 302
ok(c.post("/auth/logout"), 302)

# Admin
r = c.post("/auth/login", data={"email": ADMIN_EMAIL, "password": "Admin1234"})
assert r.status_code == 302 and "/admin" in r.headers["Location"]
for url in ["/admin/", "/admin/productos", "/admin/productos?status=low_stock&q=elf", "/admin/productos/nuevo", f"/admin/productos/{pid}",
            f"/admin/productos/{pid}/stock", "/admin/stock", "/admin/precios", "/admin/categorias", "/admin/categorias/nueva",
            "/admin/marcas", "/admin/marcas/nueva", "/admin/descuentos", "/admin/descuentos/nuevo", "/admin/descuentos/1",
            "/admin/clientes", "/admin/clientes?q=ana", "/admin/clientes/nuevo", "/admin/pedidos",
            "/admin/pedidos?status=pending&from=2020-01-01&to=2030-01-01", "/admin/reportes", "/admin/reportes?from=2020-01-01&to=2030-12-31"]:
    ok(c.get(url), msg=url)
r = ok(c.get("/admin/reportes/exportar.csv")); assert r.data.startswith("﻿".encode())
r = ok(c.get("/admin/reportes/exportar.pdf")); assert r.data[:4] == b"%PDF"
# Crear categoría, marca y producto con imagen
assert c.post("/admin/categorias/nueva", data={"name": "Kits Pro", "is_active": "y"}).status_code == 302
assert c.post("/admin/marcas/nueva", data={"name": "Voopoo", "is_active": "y"}).status_code == 302
import io
from PIL import Image
buf = io.BytesIO(); Image.new("RGB", (300, 300), "purple").save(buf, "PNG"); buf.seek(0)
with app.app_context():
    from app.models import Brand, Category
    cid = Category.query.filter_by(name="Kits Pro").one().id; bid = Brand.query.filter_by(name="Voopoo").one().id
r = c.post("/admin/productos/nuevo", data={"name": "Voopoo Drag <script>alert(1)</script>", "sku": "vp-001", "category_id": cid, "brand_id": bid,
        "price": "45000", "stock": "10", "min_stock": "2", "is_active": "y", "images": (buf, "foto.png")}, content_type="multipart/form-data")
assert r.status_code == 302, r.get_data(as_text=True)[:2000]
new_id = int(r.headers["Location"].rstrip("/").split("/")[-1])
page = ok(c.get(f"/admin/productos/{new_id}")).get_data(as_text=True)
assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page  # XSS escapado
# archivo falso con extensión de imagen
r = c.post(f"/admin/productos/{new_id}", data={"name": "Voopoo Drag", "sku": "VP-001", "category_id": cid, "brand_id": bid, "price": "45000",
        "min_stock": "2", "is_active": "y", "images": (io.BytesIO(b"<?php echo 1; ?>"), "shell.png")}, content_type="multipart/form-data")
assert "no es una imagen" in r.get_data(as_text=True)
# Stock
assert c.post(f"/admin/productos/{new_id}/stock", data={"change_qty": "5", "reason": "purchase"}).status_code == 302
r = c.post(f"/admin/productos/{new_id}/stock", data={"change_qty": "-500", "reason": "adjustment"}, follow_redirects=True)
assert "no puede quedar negativo" in r.get_data(as_text=True)
# Precios masivos
assert c.post("/admin/precios", data={"percent": "10", "category_id": cid, "brand_id": 0}).status_code == 302
with app.app_context():
    assert float(db.session.get(Product, new_id).price) == 49500.0
# Descuento
r = c.post("/admin/descuentos/nuevo", data={"name": "Promo", "discount_type": "percent", "value": "20", "target": "product", "product_id": new_id,
        "category_id": 0, "starts_at": "2020-01-01T00:00", "ends_at": "2035-01-01T00:00", "is_active": "y"})
assert r.status_code == 302, r.get_data(as_text=True)[:1500]
r = c.post("/admin/descuentos/nuevo", data={"name": "Mala", "discount_type": "percent", "value": "150", "target": "category", "product_id": 0,
        "category_id": cid, "starts_at": "2020-01-01T00:00", "ends_at": "2019-01-01T00:00"})
assert r.status_code == 200 and "no puede superar 100" in r.get_data(as_text=True)
# Cliente ABM
r = c.post("/admin/clientes/nuevo", data=dict(first_name="Pepe", last_name="Admin", email="pepe@test.com", birth_date="1980-02-02", password="Clave1234", is_active="y"))
assert r.status_code == 302, r.get_data(as_text=True)[:1500]
# Pedido: cambio de estados con transición inválida
with app.app_context():
    o = Order.query.join(Order.status).filter_by(code="pending").first(); oid = o.id
assert c.post(f"/admin/pedidos/{oid}", data={"status": "paid", "comment": "Pago acreditado"}).status_code == 302
assert c.post(f"/admin/pedidos/{oid}", data={"status": "delivered"}, follow_redirects=True).status_code == 200
with app.app_context():
    assert db.session.get(Order, oid).status.code == "paid"
# Borrar producto sin ventas
assert c.post(f"/admin/productos/{new_id}/eliminar").status_code == 302
# SQL injection en búsqueda
ok(c.get("/productos?q=' OR 1=1 -- ")); ok(c.get("/admin/pedidos?q=%27%3B DROP TABLE users;--"))
# Admin no puede usar carrito
assert c.get("/carrito/").status_code == 302

# CSRF habilitado: POST sin token rechazado
app.config["WTF_CSRF_ENABLED"] = True
c2 = app.test_client()
assert c2.post("/auth/login", data={"email": "x@x.com", "password": "x"}).status_code == 400
# Headers de seguridad
h = c2.get("/").headers
assert "Content-Security-Policy" in h and h["X-Frame-Options"] == "DENY"
print("SMOKE TEST OK")
