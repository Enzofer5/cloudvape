"""Funciones auxiliares sin estado: slugs, formato de moneda, fechas, paginación."""
import re
import unicodedata
from datetime import date, datetime, time
from decimal import Decimal
from urllib.parse import urlparse

from flask import request


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "item"


def unique_slug(model, text: str, exclude_id=None) -> str:
    """Genera un slug único para el modelo indicado (agrega sufijo -2, -3...)."""
    from ..extensions import db

    base = slugify(text)[:150]
    slug, n = base, 2
    with db.session.no_autoflush:
        while True:
            q = model.query.filter_by(slug=slug)
            if exclude_id is not None:
                q = q.filter(model.id != exclude_id)
            if not q.first():
                return slug
            slug = f"{base}-{n}"
            n += 1


def format_money(value) -> str:
    """Formato argentino: $ 12.345,67"""
    if value is None:
        value = Decimal("0")
    s = f"{Decimal(value):,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {s}"


def format_datetime(value, fmt="%d/%m/%Y %H:%M") -> str:
    return value.strftime(fmt) if value else ""


def parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def day_start(d: date) -> datetime:
    return datetime.combine(d, time.min)


def day_end(d: date) -> datetime:
    return datetime.combine(d, time.max)


def is_safe_redirect(target: str | None) -> bool:
    """Evita open-redirects: solo permite rutas relativas del mismo host."""
    if not target:
        return False
    ref = urlparse(request.host_url)
    test = urlparse(target)
    return (not test.scheme and not test.netloc and target.startswith("/")) or (
        test.scheme in ("http", "https") and test.netloc == ref.netloc
    )


def page_arg(name: str = "page") -> int:
    try:
        return max(int(request.args.get(name, 1)), 1)
    except (TypeError, ValueError):
        return 1
