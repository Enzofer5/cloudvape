# CloudVape — Tienda online de vapes (Flask + MySQL)

Tienda online completa con catálogo, carrito, checkout, área de cliente y panel de administración.
Backend Python/Flask con arquitectura en capas (MVC + servicios), base MySQL en 3FN y frontend responsive
en HTML5/CSS3/JavaScript sin dependencias externas.

---

## 0. Verlo funcionando YA (modo demo, sin MySQL)

1. Instalá Python desde https://www.python.org/downloads/ (al instalar, tildá **"Add python.exe to PATH"**).
2. Hacé doble clic en **`INICIAR.bat`**.
3. La primera vez instala todo y carga productos de ejemplo (tarda unos minutos). Después se abre solo el navegador en http://127.0.0.1:5000

| Acceso | Usuario | Contraseña |
|---|---|---|
| Panel admin (`/admin`) | admin@demo.com | Admin1234 |
| Cliente | cliente@demo.com | Demo1234 |

El modo demo usa una base SQLite (`instance/vapeshop_demo.db`) creada a partir de los mismos modelos.
Para pasar a MySQL seguí los pasos de abajo y reemplazá en `.env` la línea `DATABASE_URL` por las variables `DB_*`.
Para empezar la demo de cero, borrá la carpeta `instance`.

## 1. Requisitos

- Python 3.10 o superior
- MySQL 8.0.16+ (o MariaDB 10.6+)

## 2. Instalación paso a paso (Windows)

```powershell
# 1) Entrar a la carpeta del proyecto
cd vapeshop

# 2) Crear y activar el entorno virtual
python -m venv venv
venv\Scripts\activate

# 3) Instalar dependencias
pip install -r requirements.txt

# 4) Crear la base y el usuario MySQL (editá antes la contraseña dentro del archivo)
mysql -u root -p < database\create_database.sql

# 5) Crear el archivo de configuración
copy .env.example .env
#    -> editá .env: SECRET_KEY, DB_USER, DB_PASSWORD, etc.
#    -> generá una SECRET_KEY con:  python -c "import secrets; print(secrets.token_hex(32))"

# 6) Crear las tablas
flask init-db

# 7) Crear el usuario administrador
flask create-admin

# 8) (Opcional) Cargar datos de demostración: 30 productos con imágenes, clientes y 60 pedidos
flask seed-demo

# 9) Levantar el servidor
flask run
```

Abrí http://127.0.0.1:5000 · Panel admin: http://127.0.0.1:5000/admin
Cliente demo (si corriste `seed-demo`): `cliente@demo.com` / `Demo1234`

En Linux/macOS es igual, cambiando `venv\Scripts\activate` por `source venv/bin/activate` y `copy` por `cp`.

> Alternativa al paso 6: `mysql -u vapeshop_user -p vapeshop < database/schema.sql`

### Producción

- `FLASK_ENV=production` en `.env` (exige `SECRET_KEY` y activa cookies `Secure`).
- Servir con un WSGI: `pip install waitress` y `waitress-serve --port=8000 run:app` (Windows) o `gunicorn run:app` (Linux), detrás de Nginx con HTTPS.
- Configurar SMTP en `.env` para que el mail de recuperación de contraseña se envíe de verdad (sin SMTP el enlace se imprime en la consola del servidor).

---

## 3. Arquitectura

```
Navegador ──► Controladores (Blueprints) ──► Servicios (lógica de negocio) ──► Modelos (SQLAlchemy) ──► MySQL
                 │   ▲                           │
                 ▼   │                           └─ utils (uploads, mail, helpers)
            Formularios (WTForms + CSRF)
                 │
                 ▼
            Vistas (Jinja2 + CSS + JS)
```

| Capa | Responsabilidad |
|---|---|
| **Modelos** | Mapeo objeto-relacional de cada tabla, relaciones y propiedades calculadas. No conocen HTTP. |
| **Servicios** | Reglas de negocio: carrito, checkout transaccional, descuentos, stock, reportes, exportaciones. |
| **Controladores** | Reciben la request, validan el formulario, llaman al servicio y devuelven la vista. |
| **Formularios** | Validación server-side de todos los datos de entrada + token CSRF. |
| **Vistas** | Plantillas Jinja2 con autoescape; JS sin scripts inline (compatible con CSP). |

## 4. Estructura de carpetas

```
vapeshop/
├── run.py                        Punto de entrada
├── config.py                     Configuración por entorno (lee .env)
├── requirements.txt              Dependencias
├── .env.example                  Plantilla de variables sensibles
├── database/
│   ├── create_database.sql       Crea la base y el usuario con mínimos privilegios
│   └── schema.sql                Tablas, claves, restricciones, vista y datos de referencia
├── tests/smoke_test.py           Prueba end-to-end (usar sobre una base de desarrollo)
└── app/
    ├── __init__.py               Application factory, headers de seguridad, errores
    ├── extensions.py             Instancias de SQLAlchemy, LoginManager, CSRF
    ├── cli.py                    Comandos: init-db, create-admin, seed-demo
    ├── models/
    │   ├── user.py               Role, User, Address, PasswordResetToken
    │   ├── catalog.py            Category, Brand, Product, ProductImage, Discount, StockMovement
    │   └── order.py              CartItem, OrderStatus, Order, OrderItem, OrderStatusHistory
    ├── services/
    │   ├── auth_service.py       Registro, login, cambio y recuperación de contraseña
    │   ├── catalog_service.py    Búsqueda, filtros, orden y paginación del catálogo
    │   ├── pricing_service.py    Cálculo del mejor descuento vigente (cache por request)
    │   ├── cart_service.py       Carrito en sesión (invitado) y en BD (cliente), fusión al login
    │   ├── order_service.py      Checkout con bloqueo de stock, máquina de estados, cancelaciones
    │   ├── product_service.py    ABM de productos, imágenes, ajustes de stock, precios masivos
    │   ├── customer_service.py   ABM de clientes
    │   ├── report_service.py     Estadísticas y agregaciones SQL para dashboard y reportes
    │   └── export_service.py     Exportación CSV y PDF
    ├── forms/                    auth.py, account.py (perfil/checkout), admin.py, validators.py
    ├── controllers/
    │   ├── shop.py               Portada, catálogo, detalle
    │   ├── auth.py               Registro, login, logout, recuperación
    │   ├── cart.py               Carrito y checkout
    │   ├── account.py            Perfil, direcciones, historial y estado de pedidos
    │   └── admin/                dashboard, products, catalog (categorías/marcas/descuentos),
    │                             customers, orders, reports
    ├── utils/                    decorators (roles), helpers, uploads, mailer, rate_limit
    ├── templates/                base, partials, shop, auth, cart, account, admin, errors, emails
    └── static/                   css (style, admin), js (main, admin), img, uploads/products
```

## 5. Modelo de datos (3FN)

```
roles 1───N users 1───N addresses
               │  1───N password_reset_tokens
               │  1───N cart_items N───1 products
               │  1───N orders 1───N order_items N───1 products
               │            1───N order_status_history N───1 order_statuses
               │            N───1 order_statuses
categories 1───N products N───1 brands
products 1───N product_images
products 1───N stock_movements (auditoría, con usuario y pedido opcional)
discounts N───1 products  |  discounts N───1 categories   (exactamente uno, por CHECK)
```

Decisiones de diseño:

- **Sin totales almacenados**: subtotal, descuento y total del pedido se calculan desde `order_items`
  (evita dependencias transitivas). La vista `v_order_totals` los expone para consultas SQL directas.
- **Precios y dirección históricos**: `order_items.unit_price/list_price` y los campos `ship_*` de `orders`
  guardan el valor *al momento de la compra*. No es redundancia: es un hecho distinto del precio actual.
- **Estados en tabla propia** (`order_statuses`) y transiciones controladas en `OrderStatus.TRANSITIONS`.
- **Integridad**: PK en todas las tablas, FK con `ON DELETE` explícito, `UNIQUE` (email, SKU, slugs,
  producto por carrito), `CHECK` (precio ≥ 0, stock ≥ 0, cantidad > 0, porcentaje ≤ 100, fechas coherentes).
- Productos y clientes con ventas **no se borran físicamente**: se desactivan para no romper el historial.

## 6. Seguridad implementada

| Riesgo | Medida |
|---|---|
| Contraseñas | Hash con Werkzeug (scrypt/pbkdf2 + salt). Nunca se guardan en texto plano. |
| SQL Injection | Todas las consultas vía ORM / parámetros enlazados; comodines de LIKE escapados. |
| XSS | Autoescape de Jinja2, `textContent` en JS, Content-Security-Policy sin scripts inline. |
| CSRF | Token en todos los formularios y en las llamadas AJAX (Flask-WTF). |
| Sesiones | Cookies `HttpOnly`, `SameSite=Lax`, `Secure` en producción, regeneración al loguear, expiración. |
| Control de acceso | `@admin_required` y `@customer_required`; todo `/admin` y `/mi-cuenta` protegido. Cada cliente solo ve sus pedidos/direcciones. |
| Fuerza bruta | Bloqueo de 15 min tras 5 intentos fallidos de login por IP+email. |
| Enumeración de usuarios | Mismo mensaje en login y recuperación exista o no el email. |
| Recuperación | Token aleatorio de un solo uso, guardado hasheado (SHA-256), expira en 30 min. |
| Subida de archivos | Extensión permitida + verificación real con Pillow + re-codificación a WEBP con nombre aleatorio; límite 8 MB. |
| Open redirect | El parámetro `next` solo acepta rutas del propio sitio. |
| CSV injection | Celdas que empiezan con `= + - @` se neutralizan al exportar. |
| Secretos | Credenciales y `SECRET_KEY` solo en `.env` (excluido por `.gitignore`). |
| Headers | CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, HSTS en HTTPS, `no-store` en páginas privadas. |
| Mayoría de edad | Aviso +18 al ingresar, fecha de nacimiento validada en el registro y confirmación en el checkout. |

## 7. Funcionalidades

**Clientes**: registro, login, recuperación de contraseña, catálogo con búsqueda y filtros (categoría, marcas,
precio, nicotina, stock, orden), detalle con galería, carrito (AJAX, persiste al loguear), checkout,
historial, seguimiento de estado con línea de tiempo, cancelación de pedidos pendientes, perfil y direcciones.

**Administrador**: dashboard (ventas del día/mes, gráfico de 30 días, pedidos por estado, top productos,
stock bajo), ABM de productos con múltiples imágenes, categorías, marcas, descuentos por producto o categoría
con vigencia, movimientos de stock auditados, actualización masiva de precios, ABM de clientes, gestión de
pedidos con cambio de estado (repone stock al cancelar), reportes por rango de fechas y exportación CSV / PDF.

## 8. Prueba automática

Sobre una base de **desarrollo** con datos demo:

```bash
flask init-db --yes && flask seed-demo
flask create-admin --email admin@demo.com --first-name Admin --last-name Tienda --password Admin1234
python tests/smoke_test.py
```

Recorre registro, carrito, checkout, cancelación, recuperación de contraseña, todo el panel admin,
exportaciones, intentos de XSS / SQL injection / archivo falso, CSRF y headers de seguridad.
