from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any
from aiosqlite import connect, Connection, Row
from collections.abc import Generator


@dataclass
class User:
    _id: int
    telegram_id: int
    created_at: datetime
    invited_at: datetime


def connect_db(db_url):
    """
    solid — Dependency Inversion
    Top level modules should not depend
    on lower level modules,
    so on I am taking db path as parameter
    """

    def decorator(func):
        wraps(func)

        async def wrapper(*args, **kwargs):
            async with connect(db_url) as db:
                return await func(db, *args, **kwargs)

        return wrapper

    return decorator


@connect_db(db_url="market_bot.db")
async def create_db(db: Connection) -> None:
    await db.execute("""create table if not exists user (
telegram_id integer,
created_at timestamp default current_timestamp,
invited_at timestamp,
primary key(telegram_id))""")


class UserManager:
    @staticmethod
    @connect_db(db_url="market_bot.db")
    async def create(db: Connection, telegram_id: int) -> None:
        await UserManager.find(telegram_id)
        await db.execute("insert into user(telegram_id) values (?)", (telegram_id,))
        await db.commit()

    @staticmethod
    @connect_db(db_url="")
    async def update(db: Connection, telegram_id: int) -> None:
        await db.execute("update user set invited_at = current_timestamp where telegram_id = ?", (telegram_id,))
        await db.commit()

    @staticmethod
    @connect_db(db_url="market_bot.db")
    async def find(db: Connection, telegram_id: int) -> int:
        """Returns the firs entry that matches the specific telegram id if found"""
        db.row_factory = Row
        row: Row
        async with db.execute("select * from user where telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
        return row['telegram_id']

    @staticmethod
    @connect_db(db_url="market_bot.db")
    async def read_all_ids(db: Connection, not_invited_only: bool = True) -> Generator[int, Any, None]:
        """Returns a generator of all users telegram_id (to invite only or all) to use them efficiently"""
        db.row_factory = Row
        query = "select telegram_id from user"
        query += " where invited_at is not null" if not_invited_only else ""
        return (row['telegram_id'] for row in await db.execute_fetchall(query))

    @staticmethod
    @connect_db(db_url="market_bot.db")
    async def read_all_full_info(db: Connection, not_invited_only: bool = False) -> Generator[User, Any, None]:
        """Returns a generator of all users full info (to invite only or all) to use them efficiently"""

        query = "select * from user"
        query += " where invited_at is not null" if not_invited_only else ""
        return (User(row['_id'], row['telegram_id'], row['created_at'], row['invited_at'])
                for row in await db.execute_fetchall(query))
