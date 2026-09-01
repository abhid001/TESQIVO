"""Small operational CLI: ``python -m app.cli <command>``.

Commands
--------
wait-db        Block until the database answers ``SELECT 1`` (used by the entrypoint).
create-admin   Create the first System Admin. Works only while no user exists; shell
               access to the container is the authorization gate, so no bootstrap
               token is required. Prompts interactively, or pass --username / --email
               / --password for non-interactive use.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import text

from app.core.context import Ctx, Source
from app.core.db import get_sessionmaker
from app.domain import auth


async def _wait_db(retries: int = 30) -> None:
    sm = get_sessionmaker()
    for i in range(retries):
        try:
            async with sm() as s:
                await s.execute(text("SELECT 1"))
            print("database reachable")
            return
        except Exception as exc:  # noqa: BLE001
            print(f"waiting for database ({i + 1}/{retries}): {exc}")
            await asyncio.sleep(2)
    sys.exit(1)


def _prompt(label: str, current: str | None) -> str:
    if current:
        return current
    try:
        value = input(f"{label}: ").strip()
    except EOFError:
        value = ""
    if not value:
        sys.exit(f"error: {label} is required")
    return value


def _prompt_password(current: str | None) -> str:
    if current:
        return current
    first = getpass.getpass("Password (min 12 chars): ")
    second = getpass.getpass("Password (again): ")
    if first != second:
        sys.exit("error: passwords do not match")
    return first


async def _create_admin(args: argparse.Namespace) -> None:
    sm = get_sessionmaker()
    async with sm() as session:
        if not await auth.needs_setup(session):
            sys.exit("error: an administrator already exists; use the admin console to add users")
        username = _prompt("Username", args.username)
        email = _prompt("Email", args.email)
        if args.display_name:
            display_name = args.display_name
        elif args.username:  # non-interactive: default to the username
            display_name = username
        else:
            display_name = input(f"Display name [{username}]: ").strip() or username
        password = _prompt_password(args.password)
        ctx = Ctx(correlation_id="cli-create-admin", source=Source.system)
        try:
            user = await auth.create_first_admin(
                session, ctx, username=username, email=email,
                display_name=display_name, password=password,
            )
        except Exception as exc:  # noqa: BLE001
            sys.exit(f"error: {exc}")
    print(f"created System Admin '{user.username}' <{user.email}>")


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("wait-db", help="block until the database is reachable")

    ca = sub.add_parser("create-admin", help="create the first System Admin")
    ca.add_argument("--username")
    ca.add_argument("--email")
    ca.add_argument("--display-name")
    ca.add_argument("--password", help="avoid on shared shells; prefer the interactive prompt")

    args = parser.parse_args()
    if args.command == "wait-db":
        asyncio.run(_wait_db())
    elif args.command == "create-admin":
        asyncio.run(_create_admin(args))


if __name__ == "__main__":
    main()
