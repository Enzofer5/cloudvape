"""Blueprint del panel de administración. Todas sus rutas exigen rol admin."""
from flask import Blueprint

from ...utils.decorators import admin_required

bp = Blueprint("admin", __name__)


@bp.before_request
@admin_required
def protect():
    return None


# Importar los módulos registra sus rutas en el blueprint
from . import catalog, customers, dashboard, orders, products, reports  # noqa: E402,F401
