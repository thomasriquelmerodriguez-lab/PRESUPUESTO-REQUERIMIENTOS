from __future__ import annotations

import argparse
import getpass

from sqlalchemy import delete, select

from app.core.security import hash_password
from app.db.base import SessionLocal
from app.db.models import SessionRecord, User
from app.services.auth import normalize_username


def main() -> None:
    parser = argparse.ArgumentParser(description="Cambiar la clave de un usuario y cerrar sus sesiones.")
    parser.add_argument("username", help="Nombre de usuario")
    args = parser.parse_args()
    password = getpass.getpass("Nueva clave (mínimo 12 caracteres): ")
    confirmation = getpass.getpass("Repita la nueva clave: ")
    if password != confirmation:
        raise SystemExit("Las claves no coinciden.")
    if len(password) < 12:
        raise SystemExit("La clave debe tener al menos 12 caracteres.")
    if password.isdigit() or password.lower() in {"password", "contraseña", "municipalidad"}:
        raise SystemExit("La clave es demasiado predecible.")

    with SessionLocal() as db:
        user = db.execute(
            select(User).where(User.username == normalize_username(args.username))
        ).scalar_one_or_none()
        if not user:
            raise SystemExit("Usuario no encontrado.")
        user.password_hash = hash_password(password)
        user.session_version += 1
        db.execute(delete(SessionRecord).where(SessionRecord.user_id == user.id))
        db.commit()
        print(f"Clave actualizada para {user.display_name}. Todas sus sesiones fueron cerradas.")


if __name__ == "__main__":
    main()
