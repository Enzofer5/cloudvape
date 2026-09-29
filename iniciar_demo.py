"""Arranque rápido en modo demostración (no requiere MySQL).

Crea un .env con base SQLite si no existe, carga datos de ejemplo la primera vez,
abre el navegador y levanta el servidor en http://127.0.0.1:5000
"""
import os
import secrets
import threading
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
URL = "http://127.0.0.1:5000"

ADMIN_EMAIL = "admin@demo.com"
ADMIN_PASSWORD = "Admin1234"


def ensure_env():
    if os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH, "w", encoding="utf-8") as fh:
        fh.write(
            "# Generado por iniciar_demo.py (modo demostración con SQLite)\n"
            "# Para usar MySQL, reemplazá DATABASE_URL por las variables DB_* de .env.example\n"
            f"SECRET_KEY={secrets.token_hex(32)}\n"
            "DATABASE_URL=sqlite:///vapeshop_demo.db\n"
            "STORE_NAME=.vape\n"
            "SHIPPING_FLAT_COST=3500\n"
            "FREE_SHIPPING_FROM=60000\n"
        )
    print("-> Se creó el archivo .env (modo demo con SQLite).")


def main():
    ensure_env()
    from sqlalchemy import inspect

    from app import create_app
    from app.cli import create_admin, init_db, seed_demo
    from app.extensions import db

    app = create_app("development")
    app.config["DEBUG"] = False

    from app.models import User

    with app.app_context():
        first_time = not inspect(db.engine).has_table("users") or User.query.count() == 0
    if first_time:
        print("-> Primera ejecución: creando base de datos y cargando productos de ejemplo...")
        runner = app.test_cli_runner()
        ctx = app.app_context()
        ctx.push()
        for cmd, args in ((init_db, ["--yes"]), (seed_demo, []),
                          (create_admin, ["--email", ADMIN_EMAIL, "--first-name", "Admin",
                                          "--last-name", "Tienda", "--password", ADMIN_PASSWORD])):
            result = runner.invoke(cmd, args)
            print(result.output.strip())
            if result.exit_code != 0:
                raise SystemExit(f"Error ejecutando {cmd.name}: {result.exception}")
        ctx.pop()

    print("\n" + "=" * 60)
    print(f"  Tienda:  {URL}")
    print(f"  Admin:   {URL}/admin   ->  {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print("  Cliente: cliente@demo.com / Demo1234")
    print("  Para detener el servidor cerrá esta ventana o presioná CTRL+C")
    print("=" * 60 + "\n")

    threading.Timer(1.5, lambda: webbrowser.open(URL)).start()
    app.run(host="127.0.0.1", port=5000, use_reloader=False)


if __name__ == "__main__":
    main()
