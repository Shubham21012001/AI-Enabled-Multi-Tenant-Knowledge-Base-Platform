"""Admin CLI.

    python -m app.cli create-superadmin --email root@example.com --name "Platform Admin"

The password is read interactively (never from argv, which ends up in shell history).
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User
from app.models.enums import Role
from app.schemas.auth import _check_password


def create_superadmin(email: str, name: str) -> None:
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match")
    try:
        _check_password(password)
    except ValueError as exc:
        sys.exit(str(exc))
    db = SessionLocal()
    try:
        email = email.strip().lower()
        if db.scalar(select(User).where(User.email == email)):
            sys.exit("A user with this email already exists")
        db.add(User(email=email, full_name=name, hashed_password=hash_password(password), role=Role.SUPER_ADMIN.value))
        db.commit()
        print(f"Super admin {email} created")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-superadmin")
    p.add_argument("--email", required=True)
    p.add_argument("--name", default="Platform Admin")
    args = parser.parse_args()
    if args.command == "create-superadmin":
        create_superadmin(args.email, args.name)


if __name__ == "__main__":
    main()
