"""Operator commands. Run from backend/: `uv run python -m app.cli create-admin --email ...`."""

import argparse
import asyncio
import getpass
import sys
from datetime import UTC, datetime

from app.db.session import SessionFactory
from app.services import auth as auth_service
from app.services import demo

MIN_PASSWORD_LENGTH = 8


async def create_admin(email: str, name: str, password: str) -> None:
    async with SessionFactory() as session:
        admin = await auth_service.create_admin(session, email=email, password=password, name=name)
    print(f"Admin created: {admin.email} ({admin.id})")


async def seed_demo(prune_days: int | None) -> None:
    async with SessionFactory() as session:
        result = await demo.seed(session, now=datetime.now(UTC))
        print(
            f"Courts created: {result.courts_created}, players created: {result.players_created},"
            f" reservations created: {result.reservations_created}"
        )
        if prune_days is not None:
            removed = await demo.prune(session, older_than_days=prune_days)
            print(f"Old reservations removed: {removed}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="create a user with the admin role")
    admin.add_argument("--email", required=True)
    admin.add_argument("--name", required=True)
    seed = commands.add_parser(
        "seed-demo", help="create the demo courts, sample players and reservations (idempotent)"
    )
    seed.add_argument(
        "--prune-days",
        type=int,
        help="also delete non-admin reservations that ended more than this many days ago",
    )
    args = parser.parse_args(argv)

    if args.command == "seed-demo":
        asyncio.run(seed_demo(args.prune_days))
        return 0

    # Asked interactively so the password never lands in the shell history.
    password = getpass.getpass("Password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Password must have at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1
    if password != getpass.getpass("Repeat password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 1

    try:
        asyncio.run(create_admin(args.email, args.name, password))
    except auth_service.EmailAlreadyRegistered:
        print(f"{args.email} is already registered.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
