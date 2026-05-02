import argparse
import asyncio
import getpass
import os
from dotenv import load_dotenv

from app.auth import get_password_hash, create_service_token
from app.database import async_session
from app.models import User, Photo
from sqlalchemy import select

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/db/sprout.db")
PHOTO_STORAGE_PATH = os.getenv("PHOTO_STORAGE_PATH", "./data/photos")


async def create_user(args):
    if not args.password:
        password = getpass.getpass("Password: ")
    else:
        password = args.password

    async with async_session() as db:
        user = User(
            username=args.username,
            display_name=args.display_name,
            hashed_password=get_password_hash(password),
        )
        db.add(user)
        await db.commit()
    print(f"User {args.username} created.")


async def create_token(args):
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == args.username))
        user = result.scalar_one_or_none()
        if not user:
            print("User not found.")
            return
        token = create_service_token(user.id, user.username)
        print(token)


async def cleanup_orphans(args):
    import os

    async with async_session() as db:
        result = await db.execute(select(Photo.original_path, Photo.thumbnail_path))
        db_paths = set()
        for orig, thumb in result:
            db_paths.add(orig)
            db_paths.add(thumb)

    to_delete = []
    for root, dirs, files in os.walk(PHOTO_STORAGE_PATH):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, PHOTO_STORAGE_PATH)
            if rel_path not in db_paths:
                to_delete.append(full_path)

    if args.dry_run:
        for path in to_delete:
            print(f"Would delete {path}")
    else:
        for path in to_delete:
            os.remove(path)
            print(f"Deleted {path}")


def main():
    parser = argparse.ArgumentParser(description="Sprout CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-user
    create_user_parser = subparsers.add_parser("create-user", help="Create a new user")
    create_user_parser.add_argument("--username", required=True, help="Username")
    create_user_parser.add_argument("--display-name", help="Display name")
    create_user_parser.add_argument(
        "--password", help="Password (will prompt if not provided)"
    )

    # create-token
    create_token_parser = subparsers.add_parser(
        "create-token", help="Create a service token for a user"
    )
    create_token_parser.add_argument("--username", required=True, help="Username")

    # cleanup-orphans
    cleanup_parser = subparsers.add_parser(
        "cleanup-orphans", help="Clean up orphaned photo files"
    )
    cleanup_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be deleted without deleting",
    )

    args = parser.parse_args()

    if args.command == "create-user":
        asyncio.run(create_user(args))
    elif args.command == "create-token":
        asyncio.run(create_token(args))
    elif args.command == "cleanup-orphans":
        asyncio.run(cleanup_orphans(args))


if __name__ == "__main__":
    main()
