"""Exportación de reportes a CSV y PDF."""
import csv
import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from ..utils.helpers import format_datetime, format_money

ORDER_HEADERS = ["Pedido", "Fecha", "Cliente", "Email", "Estado", "Pago",
                 "Unidades", "Subtotal", "Descuentos", "Envío", "Total"]


def _order_row(o, money=lambda v: f"{v:.2f}"):
    return [
        o.order_number, format_datetime(o.created_at), o.user.full_name, o.user.email,
        o.status.name, o.payment_label, o.items_count,
        money(o.subtotal), money(o.discount_total), money(o.shipping_cost), money(o.total),
    ]


def _csv_safe(value):
    """Previene CSV/formula injection al abrir el archivo en Excel."""
    s = str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def orders_csv(orders) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(ORDER_HEADERS)
    for o in orders:
        writer.writerow([_csv_safe(v) for v in _order_row(o)])
    # BOM para que Excel reconozca UTF-8 (acentos)
    return ("﻿" + buf.getvalue()).encode("utf-8")


def orders_pdf(orders, totals, start: date, end: date, store_name: str, top=None, by_category=None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1.2 * cm, rightMargin=1.2 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.2 * cm,
                            title=f"Reporte de ventas {start} a {end}")
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"{store_name} — Reporte de ventas", styles["Title"]),
        Paragraph(f"Período: {start:%d/%m/%Y} al {end:%d/%m/%Y}", styles["Normal"]),
        Spacer(1, 0.4 * cm),
    ]

    summary = Table([
        ["Pedidos válidos", "Facturación", "Descuentos otorgados", "Unidades", "Ticket promedio"],
        [totals.orders, format_money(totals.revenue), format_money(totals.discounts),
         totals.units, format_money(totals.avg_ticket)],
    ], hAlign="LEFT")
    summary.setStyle(_table_style())
    story += [summary, Spacer(1, 0.5 * cm)]

    if top:
        story.append(Paragraph("Productos más vendidos", styles["Heading3"]))
        t = Table([["SKU", "Producto", "Unidades", "Facturación"]] +
                  [[p["sku"], p["name"], p["units"], format_money(p["revenue"])] for p in top], hAlign="LEFT")
        t.setStyle(_table_style())
        story += [t, Spacer(1, 0.5 * cm)]

    if by_category:
        story.append(Paragraph("Ventas por categoría", styles["Heading3"]))
        t = Table([["Categoría", "Unidades", "Facturación"]] +
                  [[c["name"], c["units"], format_money(c["revenue"])] for c in by_category], hAlign="LEFT")
        t.setStyle(_table_style())
        story += [t, Spacer(1, 0.5 * cm)]

    story.append(Paragraph("Detalle de pedidos", styles["Heading3"]))
    headers = ["Pedido", "Fecha", "Cliente", "Estado", "Pago", "Unid.", "Subtotal", "Desc.", "Envío", "Total"]
    rows = [[o.order_number, format_datetime(o.created_at), Paragraph(o.user.full_name, styles["BodyText"]),
             o.status.name, o.payment_method, o.items_count, format_money(o.subtotal),
             format_money(o.discount_total), format_money(o.shipping_cost), format_money(o.total)]
            for o in orders]
    if not rows:
        rows = [["Sin pedidos en el período"] + [""] * 9]
    table = Table([headers] + rows, repeatRows=1,
                  colWidths=[3.2 * cm, 3 * cm, 4.5 * cm, 2.8 * cm, 1.8 * cm, 1.2 * cm,
                             2.6 * cm, 2.3 * cm, 2.2 * cm, 2.8 * cm])
    table.setStyle(_table_style(font_size=8))
    story.append(table)

    doc.build(story)
    return buf.getvalue()


def _table_style(font_size=9):
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d4d4d8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f5")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
