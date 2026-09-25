from __future__ import annotations

import argparse
import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import SessionLocal
from app.db.models import Area, User, UserArea
from app.services.auth import normalize_username

VALID_AREAS = {"municipal", "salud", "educacion"}
VALID_ROLES = {"budget_manager", "area_user"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear un usuario del sistema.")
    parser.add_argument("username")
    parser.add_argument("--name", required=True, dest="display_name")
    parser.add_argument("--role", choices=sorted(VALID_ROLES), default="area_user")
    parser.add_argument("--areas", required=True, help="Áreas separadas por coma")
    args = parser.parse_args()

    areas = {item.strip().lower() for item in args.areas.split(",") if item.strip()}
    if not areas or not areas.issubset(VALID_AREAS):
        raise SystemExit("Áreas válidas: municipal, salud, educacion.")
    if args.role == "budget_manager":
        areas = set(VALID_AREAS)

    password = getpass.getpass("Clave inicial (mínimo 12 caracteres): ")
    confirmation = getpass.getpass("Repita la clave: ")
    if password != confirmation or len(password) < 12:
        raise SystemExit("Las claves no coinciden o tienen menos de 12 caracteres.")

    with SessionLocal() as db:
        username = normalize_username(args.username)
        if db.execute(select(User.id).where(User.username == username)).scalar_one_or_none():
            raise SystemExit("El usuario ya existe.")
        area_rows = {
            row.slug: row
            for row in db.execute(select(Area).where(Area.slug.in_(areas))).scalars()
        }
        if set(area_rows) != areas:
            raise SystemExit("Una o más áreas no existen en la base de datos.")
        user = User(
            username=username,
            display_name=args.display_name.strip()[:120],
            role=args.role,
            password_hash=hash_password(password),
        )
        db.add(user)
        db.flush()
        for slug in sorted(areas):
            db.add(UserArea(user_id=user.id, area_id=area_rows[slug].id))
        db.commit()
        print(f"Usuario {user.display_name} creado con acceso a: {', '.join(sorted(areas))}.")


if __name__ == "__main__":
    main()
