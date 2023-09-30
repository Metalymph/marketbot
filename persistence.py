from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any
from aiosqlite import connect, Connection, Row
from collections.abc import Generator


@dataclass
class User:
    telegram_id: int
    username: str
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
username text not null,
created_at timestamp default current_timestamp,
invited_at timestamp,
primary key(telegram_id))""")


class UserManager:
    @staticmethod
    @connect_db(db_url="market_bot.db")
    async def create(db: Connection,
                     telegram_id: int,
                     username: str) -> int:
        if await UserManager.find(telegram_id) > 0:
            return 0
        await db.execute("insert into user(telegram_id, username) values (?, ?)", (telegram_id, username))
        await db.commit()
        return telegram_id

    @staticmethod
    @connect_db(db_url="market_bot.db")
    async def find(db: Connection,
                   telegram_id: int) -> int:
        """Returns the firs entry that matches the specific telegram id if found"""
        db.row_factory = Row
        row: Row
        async with db.execute("select * from user where telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
        return 0 if row is None else row['telegram_id']

    @staticmethod
    @connect_db(db_url="market_bot.db")
    async def read_all(db: Connection,
                       until_to: datetime,
                       not_invited_only: bool = False,
                       only_ids: bool = False
                       ) -> Generator[User, Any, None]:
        """Returns a generator of all users full info (to invite only or all) to use them efficiently"""

        db.row_factory = Row
        param = "telegram_id" if only_ids else "*"
        query = f'select {param} from user where user.created_at <= ?'
        query += " where invited_at is null" if not_invited_only else ""

        return \
            (row['telegram_id'] for row in await db.execute_fetchall(query)) if only_ids else \
            (User(row['telegram_id'], row['username'], row['created_at'], row['invited_at'])
             for row in await db.execute_fetchall(query, [until_to.strftime("%Y/%m/%d %H:%M:%S")]))

    @staticmethod
    @connect_db(db_url="market_bot.db")
    async def update_to_invited(db: Connection,
                                telegram_id: int) -> None:
        await db.execute("update user set invited_at = current_timestamp where telegram_id = ?",
                         (telegram_id,))
        await db.commit()

    @staticmethod
    @connect_db(db_url="market_bot.db")
    async def delete_all(db: Connection) -> None:
        await db.execute("delete from user")
        await db.commit()
