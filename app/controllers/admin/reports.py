"""Reportes de ventas con filtros por fecha y exportación CSV / PDF."""
from datetime import date, timedelta

from flask import Response, current_app, render_template, request

from ...services import export_service, order_service, report_service
from ...utils.helpers import day_end, day_start, parse_date
from . import bp


def _range_from_args():
    today = date.today()
    start = parse_date(request.args.get("from")) or (today - timedelta(days=29))
    end = parse_date(request.args.get("to")) or today
    if start > end:
        start, end = end, start
    if (end - start).days > 366 * 2:  # límite razonable para no sobrecargar el servidor
        start = end - timedelta(days=366 * 2)
    status = request.args.get("status") or None
    return start, end, status


@bp.route("/reportes")
def reports():
    start, end, status = _range_from_args()
    s, e = day_start(start), day_end(end)
    series = report_service.sales_by_day(start, end)
    return render_template(
        "admin/reports/sales.html",
        start=start, end=end, status=status,
        statuses=order_service.all_statuses(),
        totals=report_service.sales_totals(s, e),
        top=report_service.top_products(s, e, 10),
        by_category=report_service.sales_by_category(s, e),
        by_brand=report_service.sales_by_brand(s, e),
        orders=report_service.orders_in_range(s, e, status),
        chart={"labels": [d["date"][5:] for d in series], "values": [float(d["revenue"]) for d in series]},
    )


@bp.route("/reportes/exportar.csv")
def reports_csv():
    start, end, status = _range_from_args()
    orders = report_service.orders_in_range(day_start(start), day_end(end), status)
    data = export_service.orders_csv(orders)
    return Response(data, mimetype="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="ventas_{start}_{end}.csv"'})


@bp.route("/reportes/exportar.pdf")
def reports_pdf():
    start, end, status = _range_from_args()
    s, e = day_start(start), day_end(end)
    pdf = export_service.orders_pdf(
        report_service.orders_in_range(s, e, status), report_service.sales_totals(s, e), start, end,
        current_app.config["STORE_NAME"], report_service.top_products(s, e, 10),
        report_service.sales_by_category(s, e),
    )
    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="ventas_{start}_{end}.pdf"'})
