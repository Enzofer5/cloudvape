-- Ejecutar UNA sola vez como root:
--   mysql -u root -p < database/create_database.sql
-- Cambiá la contraseña por una segura y usá la misma en tu archivo .env

CREATE DATABASE IF NOT EXISTS vapeshop
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'vapeshop_user'@'localhost' IDENTIFIED BY 'cambiar_password';

-- Principio de mínimo privilegio: solo lo que la app necesita sobre su base.
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES,
      CREATE VIEW, SHOW VIEW
  ON vapeshop.* TO 'vapeshop_user'@'localhost';

FLUSH PRIVILEGES;
