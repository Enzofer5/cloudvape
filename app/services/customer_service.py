"""ABM de clientes desde el panel administrador."""
from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import Order, Role, User
from .auth_service import AuthError, normalize_email
from .catalog_service import _escape_like


def search_customers(q: str, status: str, page: int, per_page: int):
    query = User.query.join(Role).filter(Role.name == Role.CUSTOMER)
    if q:
        like = f"%{_escape_like(q.strip())}%"
        query = query.filter(or_(
            User.first_name.ilike(like, escape="\\"),
            User.last_name.ilike(like, escape="\\"),
            User.email.ilike(like, escape="\\"),
            User.phone.ilike(like, escape="\\"),
        ))
    if status == "active":
        query = query.filter(User.is_active_flag.is_(True))
    elif status == "inactive":
        query = query.filter(User.is_active_flag.is_(False))
    return db.paginate(query.order_by(User.created_at.desc()), page=page, per_page=per_page, error_out=False)


def orders_count_map(user_ids) -> dict:
    if not user_ids:
        return {}
    rows = db.session.execute(
        select(Order.user_id, func.count(Order.id)).where(Order.user_id.in_(user_ids)).group_by(Order.user_id)
    ).all()
    return {r[0]: r[1] for r in rows}


def get_customer(user_id: int) -> User | None:
    return User.query.join(Role).filter(Role.name == Role.CUSTOMER, User.id == user_id).first()


def create_customer(data: dict) -> User:
    email = normalize_email(data["email"])
    if User.query.filter_by(email=email).first():
        raise AuthError("Ya existe un usuario con ese email.")
    user = User(
        role=Role.query.filter_by(name=Role.CUSTOMER).one(),
        first_name=data["first_name"].strip(), last_name=data["last_name"].strip(),
        email=email, phone=(data.get("phone") or "").strip() or None,
        birth_date=data["birth_date"], is_active_flag=data.get("is_active", True),
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return user


def update_customer(user: User, data: dict) -> User:
    email = normalize_email(data["email"])
    if User.query.filter(User.email == email, User.id != user.id).first():
        raise AuthError("Ya existe un usuario con ese email.")
    user.first_name = data["first_name"].strip()
    user.last_name = data["last_name"].strip()
    user.email = email
    user.phone = (data.get("phone") or "").strip() or None
    user.birth_date = data["birth_date"]
    user.is_active_flag = bool(data.get("is_active"))
    if data.get("password"):
        user.set_password(data["password"])
    db.session.commit()
    return user


def delete_customer(user: User) -> str:
    """Si el cliente tiene pedidos solo se desactiva (no se pierde historial)."""
    if user.orders.count():
        user.is_active_flag = False
        db.session.commit()
        return "deactivated"
    db.session.delete(user)
    db.session.commit()
    return "deleted"
