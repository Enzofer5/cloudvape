"""Application factory."""
import logging
import os
import secrets

from flask import Flask, render_template, request
from flask_wtf.csrf import CSRFError

from config import config_by_name

from .extensions import csrf, db, login_manager


def create_app(config_name: str = "development") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name["development"]))

    if not app.config.get("SECRET_KEY"):
        if config_name == "production":
            raise RuntimeError("SECRET_KEY no configurada. Definila en el archivo .env")
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        app.logger.warning("SECRET_KEY no definida: se generó una temporal (las sesiones se perderán al reiniciar).")

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    logging.basicConfig(level=logging.INFO)

    db.init_app(app)
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        _enable_sqlite_foreign_keys(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models  # noqa: F401  (registra los modelos)

    @login_manager.user_loader
    def load_user(user_id):
        user = db.session.get(models.User, int(user_id))
        return user if user and user.is_active else None

    _register_blueprints(app)
    _register_template_helpers(app)
    _register_error_handlers(app)
    _register_security_headers(app)

    from .cli import register_cli
    register_cli(app)
    return app


def _enable_sqlite_foreign_keys(app: Flask) -> None:
    """En modo demo (SQLite) se activan las claves foráneas, que SQLite trae apagadas."""
    from sqlalchemy import event

    with app.app_context():
        @event.listens_for(db.engine, "connect")
        def _fk_on(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()


def _register_blueprints(app: Flask) -> None:
    from .controllers.account import bp as account_bp
    from .controllers.admin import bp as admin_bp
    from .controllers.auth import bp as auth_bp
    from .controllers.cart import bp as cart_bp
    from .controllers.shop import bp as shop_bp

    app.register_blueprint(shop_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(cart_bp, url_prefix="/carrito")
    app.register_blueprint(account_bp, url_prefix="/mi-cuenta")
    app.register_blueprint(admin_bp, url_prefix="/admin")


def _register_template_helpers(app: Flask) -> None:
    from .services import cart_service, catalog_service
    from .services.pricing_service import price_info
    from .utils.helpers import format_datetime, format_money

    app.jinja_env.filters["money"] = format_money
    app.jinja_env.filters["dt"] = format_datetime
    app.jinja_env.globals["price_info"] = price_info

    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        is_admin_area = request.blueprint == "admin"
        cart_count, categories = 0, []
        try:
            if not is_admin_area:
                categories = catalog_service.active_categories()
                if not (current_user.is_authenticated and current_user.is_admin):
                    cart_count = cart_service.count()
        except Exception:  # la página de error debe renderizar aunque falle la BD
            db.session.rollback()
            app.logger.exception("No se pudo cargar el contexto global")
        return {
            "store_name": app.config["STORE_NAME"],
            "cart_count": cart_count,
            "nav_categories": categories,
            "free_shipping_from": app.config["FREE_SHIPPING_FROM"],
        }


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/error.html", code=403, message="No tenés permiso para acceder a esta página."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/error.html", code=404, message="La página que buscás no existe."), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("errors/error.html", code=413, message="El archivo es demasiado grande (máx. 8 MB)."), 413

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        return render_template("errors/error.html", code=400,
                               message="La sesión del formulario expiró. Volvé atrás y recargá la página."), 400

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors/error.html", code=500, message="Ocurrió un error inesperado."), 500


def _register_security_headers(app: Flask) -> None:
    csp = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; script-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )

    @app.after_request
    def set_headers(response):
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        # Las páginas privadas no deben quedar en caché del navegador
        if request.blueprint in ("account", "admin", "auth", "cart"):
            response.headers["Cache-Control"] = "no-store"
        return response
