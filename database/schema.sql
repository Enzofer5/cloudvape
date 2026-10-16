-- =====================================================================
--  CloudVape - Esquema de base de datos (MySQL 8 / MariaDB 10.6+)
--  Modelo normalizado en 3FN con integridad referencial.
--  Uso:  mysql -u vapeshop_user -p vapeshop < database/schema.sql
--        (o bien: flask init-db)
-- =====================================================================

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS order_status_history;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS order_statuses;
DROP TABLE IF EXISTS cart_items;
DROP TABLE IF EXISTS stock_movements;
DROP TABLE IF EXISTS discounts;
DROP TABLE IF EXISTS product_images;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS brands;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS password_reset_tokens;
DROP TABLE IF EXISTS addresses;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS roles;
SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- Seguridad / usuarios
-- ---------------------------------------------------------------------
CREATE TABLE roles (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name        VARCHAR(30)      NOT NULL,
    description VARCHAR(120)     NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_roles_name UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE users (
    id             INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    role_id        TINYINT UNSIGNED NOT NULL,
    first_name     VARCHAR(60)      NOT NULL,
    last_name      VARCHAR(60)      NOT NULL,
    email          VARCHAR(120)     NOT NULL,
    password_hash  VARCHAR(255)     NOT NULL,
    phone          VARCHAR(30)      NULL,
    birth_date     DATE             NOT NULL,
    is_active      TINYINT(1)       NOT NULL DEFAULT 1,
    last_login_at  DATETIME         NULL,
    created_at     DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES roles (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX ix_users_role (role_id),
    INDEX ix_users_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE addresses (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id       INT UNSIGNED NOT NULL,
    label         VARCHAR(40)  NOT NULL DEFAULT 'Casa',
    street        VARCHAR(120) NOT NULL,
    street_number VARCHAR(10)  NOT NULL,
    apartment     VARCHAR(20)  NULL,
    city          VARCHAR(80)  NOT NULL,
    province      VARCHAR(80)  NOT NULL,
    postal_code   VARCHAR(10)  NOT NULL,
    is_default    TINYINT(1)   NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    CONSTRAINT fk_addresses_user FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    INDEX ix_addresses_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- El token se guarda HASHEADO (SHA-256): si se filtra la tabla no sirve para nada.
CREATE TABLE password_reset_tokens (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id     INT UNSIGNED NOT NULL,
    token_hash  CHAR(64)     NOT NULL,
    expires_at  DATETIME     NOT NULL,
    used_at     DATETIME     NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_prt_token UNIQUE (token_hash),
    CONSTRAINT fk_prt_user FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    INDEX ix_prt_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Catálogo
-- ---------------------------------------------------------------------
CREATE TABLE categories (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name        VARCHAR(80)  NOT NULL,
    slug        VARCHAR(100) NOT NULL,
    description VARCHAR(255) NULL,
    is_active   TINYINT(1)   NOT NULL DEFAULT 1,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_categories_name UNIQUE (name),
    CONSTRAINT uq_categories_slug UNIQUE (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE brands (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name        VARCHAR(80)  NOT NULL,
    slug        VARCHAR(100) NOT NULL,
    is_active   TINYINT(1)   NOT NULL DEFAULT 1,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_brands_name UNIQUE (name),
    CONSTRAINT uq_brands_slug UNIQUE (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE products (
    id                INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    category_id       INT UNSIGNED  NOT NULL,
    brand_id          INT UNSIGNED  NOT NULL,
    sku               VARCHAR(40)   NOT NULL,
    name              VARCHAR(150)  NOT NULL,
    slug              VARCHAR(170)  NOT NULL,
    short_description VARCHAR(255)  NULL,
    description       TEXT          NULL,
    price             DECIMAL(12,2) NOT NULL,
    stock             INT           NOT NULL DEFAULT 0,
    min_stock         INT           NOT NULL DEFAULT 5,
    nicotine_mg       DECIMAL(5,2)  NULL,
    volume_ml         DECIMAL(6,2)  NULL,
    puffs             INT UNSIGNED  NULL,
    flavor            VARCHAR(80)   NULL,
    is_active         TINYINT(1)    NOT NULL DEFAULT 1,
    is_featured       TINYINT(1)    NOT NULL DEFAULT 0,
    created_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_products_sku  UNIQUE (sku),
    CONSTRAINT uq_products_slug UNIQUE (slug),
    CONSTRAINT ck_products_price     CHECK (price >= 0),
    CONSTRAINT ck_products_stock     CHECK (stock >= 0),
    CONSTRAINT ck_products_min_stock CHECK (min_stock >= 0),
    CONSTRAINT ck_products_nicotine  CHECK (nicotine_mg IS NULL OR nicotine_mg >= 0),
    CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_products_brand FOREIGN KEY (brand_id) REFERENCES brands (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX ix_products_category (category_id),
    INDEX ix_products_brand (brand_id),
    INDEX ix_products_active_price (is_active, price),
    FULLTEXT INDEX ft_products_search (name, short_description)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE product_images (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_id  INT UNSIGNED NOT NULL,
    filename    VARCHAR(255) NOT NULL,
    sort_order  SMALLINT     NOT NULL DEFAULT 0,
    is_main     TINYINT(1)   NOT NULL DEFAULT 0,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_product_images_file UNIQUE (filename),
    CONSTRAINT fk_product_images_product FOREIGN KEY (product_id) REFERENCES products (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    INDEX ix_product_images_product (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Un descuento aplica a UN producto o a UNA categoría (nunca a ambos ni a ninguno).
-- Nota: MySQL no permite CHECK sobre columnas con acciones FK CASCADE/SET NULL,
-- por eso aquí se usa RESTRICT y la aplicación elimina los descuentos asociados.
CREATE TABLE discounts (
    id             INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    name           VARCHAR(100)  NOT NULL,
    discount_type  ENUM('percent','fixed') NOT NULL,
    value          DECIMAL(12,2) NOT NULL,
    product_id     INT UNSIGNED  NULL,
    category_id    INT UNSIGNED  NULL,
    starts_at      DATETIME      NOT NULL,
    ends_at        DATETIME      NOT NULL,
    is_active      TINYINT(1)    NOT NULL DEFAULT 1,
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT ck_discounts_value   CHECK (value > 0),
    CONSTRAINT ck_discounts_percent CHECK (discount_type <> 'percent' OR value <= 100),
    CONSTRAINT ck_discounts_dates   CHECK (ends_at > starts_at),
    CONSTRAINT ck_discounts_target  CHECK ((product_id IS NULL AND category_id IS NOT NULL)
                                        OR (product_id IS NOT NULL AND category_id IS NULL)),
    CONSTRAINT fk_discounts_product FOREIGN KEY (product_id) REFERENCES products (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_discounts_category FOREIGN KEY (category_id) REFERENCES categories (id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    INDEX ix_discounts_product (product_id),
    INDEX ix_discounts_category (category_id),
    INDEX ix_discounts_period (is_active, starts_at, ends_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Carrito persistente (usuarios logueados)
-- ---------------------------------------------------------------------
CREATE TABLE cart_items (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id     INT UNSIGNED NOT NULL,
    product_id  INT UNSIGNED NOT NULL,
    quantity    INT          NOT NULL,
    added_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_cart_user_product UNIQUE (user_id, product_id),
    CONSTRAINT ck_cart_quantity CHECK (quantity > 0),
    CONSTRAINT fk_cart_user FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_cart_product FOREIGN KEY (product_id) REFERENCES products (id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Pedidos
-- ---------------------------------------------------------------------
CREATE TABLE order_statuses (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code        VARCHAR(20)      NOT NULL,
    name        VARCHAR(40)      NOT NULL,
    sort_order  TINYINT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    CONSTRAINT uq_order_statuses_code UNIQUE (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Subtotal y total NO se almacenan: se calculan desde order_items (3FN).
-- Los datos de envío son una "foto" de la dirección al momento de comprar:
-- si el cliente luego edita su dirección, el pedido histórico no debe cambiar.
CREATE TABLE orders (
    id                INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    order_number      VARCHAR(20)      NOT NULL,
    user_id           INT UNSIGNED     NOT NULL,
    status_id         TINYINT UNSIGNED NOT NULL,
    payment_method    ENUM('transfer','cash','card') NOT NULL,
    shipping_cost     DECIMAL(12,2)    NOT NULL DEFAULT 0,
    recipient_name    VARCHAR(120)     NOT NULL,
    recipient_phone   VARCHAR(30)      NOT NULL,
    ship_street       VARCHAR(120)     NOT NULL,
    ship_number       VARCHAR(10)      NOT NULL,
    ship_apartment    VARCHAR(20)      NULL,
    ship_city         VARCHAR(80)      NOT NULL,
    ship_province     VARCHAR(80)      NOT NULL,
    ship_postal_code  VARCHAR(10)      NOT NULL,
    notes             VARCHAR(500)     NULL,
    created_at        DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_orders_number UNIQUE (order_number),
    CONSTRAINT ck_orders_shipping CHECK (shipping_cost >= 0),
    CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_orders_status FOREIGN KEY (status_id) REFERENCES order_statuses (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX ix_orders_user (user_id),
    INDEX ix_orders_status (status_id),
    INDEX ix_orders_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- unit_price = precio efectivamente cobrado; list_price = precio de lista en ese momento.
CREATE TABLE order_items (
    id            INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    order_id      INT UNSIGNED  NOT NULL,
    product_id    INT UNSIGNED  NOT NULL,
    product_name  VARCHAR(150)  NOT NULL,
    list_price    DECIMAL(12,2) NOT NULL,
    unit_price    DECIMAL(12,2) NOT NULL,
    quantity      INT           NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_order_items_order_product UNIQUE (order_id, product_id),
    CONSTRAINT ck_order_items_qty   CHECK (quantity > 0),
    CONSTRAINT ck_order_items_price CHECK (unit_price >= 0 AND list_price >= unit_price),
    CONSTRAINT fk_order_items_order FOREIGN KEY (order_id) REFERENCES orders (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_order_items_product FOREIGN KEY (product_id) REFERENCES products (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX ix_order_items_product (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE order_status_history (
    id          INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    order_id    INT UNSIGNED     NOT NULL,
    status_id   TINYINT UNSIGNED NOT NULL,
    changed_by  INT UNSIGNED     NULL,
    comment     VARCHAR(255)     NULL,
    created_at  DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_osh_order FOREIGN KEY (order_id) REFERENCES orders (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_osh_status FOREIGN KEY (status_id) REFERENCES order_statuses (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_osh_user FOREIGN KEY (changed_by) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    INDEX ix_osh_order (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Movimientos de stock (auditoría)
-- ---------------------------------------------------------------------
CREATE TABLE stock_movements (
    id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_id   INT UNSIGNED NOT NULL,
    user_id      INT UNSIGNED NULL,
    order_id     INT UNSIGNED NULL,
    change_qty   INT          NOT NULL,
    reason       ENUM('initial','purchase','sale','adjustment','cancellation') NOT NULL,
    note         VARCHAR(255) NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT ck_stock_movements_qty CHECK (change_qty <> 0),
    CONSTRAINT fk_sm_product FOREIGN KEY (product_id) REFERENCES products (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_sm_user FOREIGN KEY (user_id) REFERENCES users (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_sm_order FOREIGN KEY (order_id) REFERENCES orders (id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    INDEX ix_sm_product_date (product_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Vista de apoyo para reportes (totales calculados, no almacenados)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_order_totals AS
SELECT o.id                                          AS order_id,
       SUM(oi.unit_price * oi.quantity)              AS subtotal,
       SUM((oi.list_price - oi.unit_price) * oi.quantity) AS discount_total,
       o.shipping_cost                               AS shipping_cost,
       SUM(oi.unit_price * oi.quantity) + o.shipping_cost AS total
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
GROUP BY o.id, o.shipping_cost;

-- ---------------------------------------------------------------------
-- Datos de referencia obligatorios
-- ---------------------------------------------------------------------
INSERT INTO roles (id, name, description) VALUES
    (1, 'admin',    'Administrador de la tienda'),
    (2, 'customer', 'Cliente');

INSERT INTO order_statuses (id, code, name, sort_order) VALUES
    (1, 'pending',   'Pendiente de pago', 1),
    (2, 'paid',      'Pagado',            2),
    (3, 'preparing', 'En preparación',    3),
    (4, 'shipped',   'Enviado',           4),
    (5, 'delivered', 'Entregado',         5),
    (6, 'cancelled', 'Cancelado',         6);
