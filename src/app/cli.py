from __future__ import annotations

import argparse
import os
from app.db import init_db, migrate_if_requested


def cmd_init_db(args: argparse.Namespace) -> None:
    init_db()
    print("Database initialized (tables ensured).")


def cmd_migrate(args: argparse.Namespace) -> None:
    # Force run migrations irrespective of env var
    os.environ["INVENTORY_MIGRATE"] = "1"
    migrate_if_requested()
    print("Migration completed (schema ensured).")


def main() -> None:
    parser = argparse.ArgumentParser(prog="inventory-cli", description="Inventory maintenance commands")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-db", help="Create tables if not exist")
    p_init.set_defaults(func=cmd_init_db)

    p_mig = sub.add_parser("migrate", help="Run lightweight migrations for SQLite")
    p_mig.set_defaults(func=cmd_migrate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
