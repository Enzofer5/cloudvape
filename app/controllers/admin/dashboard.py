"""Dashboard con estadísticas."""
from flask import render_template

from ...services import report_service
from . import bp


@bp.route("/")
def dashboard():
    data = report_service.dashboard_data()
    chart = {
        "labels": [d["date"][5:] for d in data["series"]],
        "values": [float(d["revenue"]) for d in data["series"]],
    }
    return render_template("admin/dashboard.html", d=data, chart=chart)
