from telegram import Update
from telegram.ext import filters, ApplicationBuilder, CommandHandler, MessageHandler
from telegram.ext import ContextTypes

import telethon.types
from telethon import TelegramClient
from telethon.tl.types import InputChannel, InputUser
from telethon.tl.custom.dialog import Dialog
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.errors.rpcerrorlist import PeerFloodError, UserPrivacyRestrictedError

from datetime import datetime, timedelta
from enum import StrEnum, auto
import logging
import os

import persistence
from persistence import create_db, UserManager

logging.basicConfig(level=logging.ERROR)


class Config:
    def __init__(self, *, admins: list[int], api_id: int, api_hash: str, bot_token: str, phone: str):
        self.admins = admins
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.phone = phone


class CommandType(StrEnum):
    CLEAN_DB = auto()
    IMPORT = auto()
    INVITE = auto()
    NO_OP = auto()
    POST = auto()
    SIGNIN = auto()
    SIGN_OUT = auto()
    STAT = auto()
    TOKEN_INIT = auto()


class Service:

    def __init__(self, config: Config):
        self.config = config
        self.last_cmd: CommandType = CommandType.NO_OP
        self.invited_users_24h: int = 0
        self.last_invite: datetime = datetime.now()

        self.scout_client: TelegramClient = (TelegramClient('real_user', config.api_id, config.api_hash)
                                             .start(phone=lambda: config.phone))
        self.bot_client: TelegramClient | None = None

        self.app = ApplicationBuilder().token(config.bot_token).build()
        self.app.add_handler(CommandHandler("clean_cache", self._clean_cache))
        self.app.add_handler(CommandHandler("clean_db", self._clean_db))
        self.app.add_handler(CommandHandler("disconnect", self._disconnect))
        self.app.add_handler(CommandHandler("start", self._start))
        self.app.add_handler(CommandHandler("import", self._import_users))
        self.app.add_handler(CommandHandler("invite", self._invite))
        self.app.add_handler(CommandHandler("listchats", self._list_chats))
        self.app.add_handler(CommandHandler("new_post", self._new_post))
        self.app.add_handler(CommandHandler("signin", self._signin))
        self.app.add_handler(CommandHandler("sendcode", self._send_code))
        self.app.add_handler(CommandHandler("signout", self._sign_out))
        self.app.add_handler(CommandHandler("stat", self._stat))
        self.app.add_handler(CommandHandler("token", self._token))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._text))

    def run(self):
        self.app.run_polling()

    async def _clean_cache(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            with os.scandir("./") as scan_iter:
                import fnmatch
                for file in scan_iter:
                    if file.is_file() and fnmatch.fnmatch(file.name, "stat_*.txt"):
                        os.remove("./" + file.name)
            await update.message.reply_text("Stats files deleted")
        except OSError as err:
            await update.message.reply_text(f"{err}")
        self.last_cmd = CommandType.NO_OP

    async def _clean_db(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Are you sure you want cleanup the database? (yes/no)")
        self.last_cmd = CommandType.CLEAN_DB

    async def _disconnect(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if (res := await self._check_client()) is not None:
            await update.message.reply_text(res)
            self.last_cmd = CommandType.NO_OP
        else:
            await self.scout_client.disconnect()
            await update.message.reply_text("Client disconnected.")
            self.last_cmd = CommandType.NO_OP

    async def _import_users(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await self._check_conn()
        await update.message.reply_text('From which public source group you want import? ')
        self.last_cmd = CommandType.IMPORT

    async def _invite(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await self._check_conn()
        await update.message.reply_text('Specify limit number of users, destination group and '
                                        'if to force already invited users. Format: (e.g: 200,hotelForAll,yes)')
        self.last_cmd = CommandType.INVITE

    async def _list_chats(self, update: Update, _: ContextTypes.DEFAULT_TYPE):
        """Lists client chats formatted"""

        if (res := await self._check_client()) is not None:
            await update.message.reply_text(res)
            self.last_cmd = CommandType.NO_OP
            return

        groups: list[str] = []
        channels: list[str] = []
        user_chats: list[str] = []
        dialog: Dialog
        async for dialog in self.scout_client.iter_dialogs():
            if dialog.is_group:
                groups.append(f"{dialog.name}: {dialog.id})")
            elif dialog.is_channel:
                channels.append(f"{dialog.name}, {dialog.id}")
            else:
                user_chats.append(f"{dialog.name}, {dialog.id}")

        groups_fmt = "\n".join(groups)
        channels_fmt = "\n".join(channels)
        user_chats_fmt = "\n".join(user_chats)

        response = (f'Groups:\n{groups_fmt}\n\n'
                    f'Channels:\n{channels_fmt}\n\n'
                    f'Private chats:\n{user_chats_fmt}')
        await update.message.reply_text(response)
        self.last_cmd = CommandType.NO_OP

    async def _new_post(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if self.bot_client.is_user_authorized() and self.bot_client.is_connected():
            await update.message.reply_text("Write your post here.")
            self.last_cmd = CommandType.POST
        else:
            await update.message.reply_text("Please use /token to login your userbot.")

    async def _send_code(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if self.scout_client.is_user_authorized():
            await update.message.reply_text("Real user already authorized.")
        else:
            await self.scout_client.send_code_request(self.config.phone)
            await update.message.reply_text(f"Auth code sent on {self.config.phone}. Use /signin to login.")
        self.last_cmd = CommandType.NO_OP

    async def _signin(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(f'Please paste the auth code received on {self.config.phone}')
        self.last_cmd = CommandType.SIGNIN

    async def _sign_out(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if (res := await self._check_client()) is not None:
            await update.message.reply_text(res)
            self.last_cmd = CommandType.NO_OP
        else:
            await update.message.reply_text("Are you sure you want log out the real user? (yes/no) ")
            self.last_cmd = CommandType.SIGN_OUT

    async def _start(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Bot entry point callback. Allowed only to admins."""

        if update.effective_user.id not in self.config.admins:
            await update.message.reply_text(
                f"Sorry {update.effective_user.first_name} you're not enabled for this service.")
            return

        await create_db()

        message: str = f'Hello {update.effective_user.first_name}!'
        if not await self.scout_client.is_user_authorized():
            _ = await self.scout_client.send_code_request(self.config.phone)
            await update.message.reply_text(f'{message}. Auth code sent to {self.config.phone}.\n'
                                            f'Call /signin command to login.')
        else:
            await self._check_conn()
            await update.message.reply_text(f'{message} Please write the bot user token for add users.')
            self.last_cmd = CommandType.TOKEN_INIT

    async def _stat(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text('From which date you want statistics? (DD-MM-YYYY). \'today\' for all.')
        self.last_cmd = CommandType.STAT

    async def _text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Text handler based on the last command"""

        response: str = ""
        message_text = update.message.text
        if message_text == "" or message_text is None:
            await update.message.reply_text("Message text empty.")
            return

        match self.last_cmd:
            case CommandType.CLEAN_DB:
                mess_to_lower = message_text.lower()
                match mess_to_lower:
                    case "yes":
                        await UserManager.delete_all()
                        response = "Database data burned. DB structure is still saved."
                        self.last_cmd = CommandType.NO_OP
                    case "no":
                        response = "Operation cancelled. Your database integrity is save."
                        self.last_cmd = CommandType.NO_OP
                    case _:
                        response = "Answer not accepted. Accepted: (yes/no). Try again!"

            case CommandType.IMPORT:
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                               text=f'Try importing users from {message_text}...')

                match await self._search_dialog(message_text):
                    case Dialog() as d:
                        user: telethon.types.User
                        users_count: int = 0
                        async for user in self.scout_client.iter_participants(d.id):
                            # skips itself and the admins
                            if user.is_self or user.id in self.config.admins:
                                continue
                            read_id = await UserManager.create(user.id, user.username)
                            if read_id > 0:
                                users_count += 1
                        response = f'Successfully imported {users_count} users from group {message_text}.'
                    case None:
                        response = f'Chat {message_text} not found in chats. Try again!'

            case CommandType.INVITE:
                try:
                    (limit_str, destination, forced) = message_text.split(',')
                    limit = int(limit_str)

                    if limit > 200:
                        await update.message.reply_text(f"{limit} is greater then max limit 200.")
                        return

                    # verifies the violation of  200+ invited in 24h
                    diff = datetime.now() - self.last_invite
                    if diff.days >= 1:
                        self.last_invite = datetime.now()
                        self.invited_users_24h = 0

                    if self.invited_users_24h == 200:
                        await update.message.reply_text(f"Daily limit reached. "
                                                        f"You've to wait until to "
                                                        f"{self.last_invite + timedelta(days=1)}")
                        return

                    match await self._search_dialog(destination):
                        case Dialog() as d:
                            # forces the API to invite also already invited users
                            is_forced = forced.lower() == "yes"
                            forced_message = "forcing" if is_forced else "not forcing"
                            await context.bot.send_message(chat_id=update.effective_chat.id,
                                                           text=f'Try inviting {limit_str} users '
                                                                f'to {destination} ({forced_message})...')

                            channel_peer_entity = await self.scout_client.get_input_entity(d.id)
                            channel_entity = InputChannel(channel_peer_entity.channel_id,
                                                          channel_peer_entity.access_hash)

                            # read the users from db and try to add them to `destination` chat
                            refused: int = 0
                            total_invited: int = 0
                            user_read: persistence.User
                            for user_read in await UserManager.read_all(
                                    include_invited=is_forced,
                                    limit=limit):

                                # check if 48 hours are passed since the last invite to user_read, if not skip
                                if (invited_datetime := user_read.invited_at) is not None:
                                    if (datetime.now() - invited_datetime).days < 2:
                                        continue

                                try:
                                    user_peer_entity = await (self.scout_client
                                                              .get_input_entity(user_read.telegram_id))
                                    user_entity = InputUser(user_peer_entity.user_id, user_peer_entity.access_hash)

                                    # if self.bot_client is None:
                                    #     raise ValueError("Bot client not initialized")
                                    await self.scout_client(InviteToChannelRequest(channel_entity, [user_entity]))
                                    await UserManager.update_to_invited(user_read.telegram_id)
                                except UserPrivacyRestrictedError as err:
                                    # is useless to keep data of a user who locks coming connections
                                    await UserManager.delete()
                                    logging.error(f"user_id:{user_read.telegram_id} -> {err}")
                                    refused += 1
                                except telethon.errors.rpcerrorlist.UserNotMutualContactError as err:
                                    # you're locked for 24/48h after the first unilateral contact (User.invited_at)
                                    logging.error(f"user_id:{user_read.telegram_id} -> {err}")
                                    refused += 1
                                except ValueError as verr:
                                    await update.message.reply_text(f"{verr}")
                                    return
                                else:
                                    total_invited += 1
                                    self.invited_users_24h += 1
                                    if self.invited_users_24h == 200:
                                        break

                            real_inv = f"{limit} users not available, only {total_invited}." \
                                if total_invited < limit else ""
                            response = (f'{real_inv} Successfully invited {total_invited-refused}/{total_invited} '
                                        f'users to {destination}. '
                                        f'{"(restriction due to limit 200 users reached)" 
                                            if self.invited_users_24h == 200 else ""}')
                        case None:
                            response = f'Group {destination} not found in chats. Try again!'
                except PeerFloodError as err:
                    logging.error(f"{err}")
                    response = ("Flood error, too many attempts."
                                "Try /disconnect or, if not works, /sign_out after 60 seconds or more.")
                except ValueError as verr:
                    response = f'{verr}.\nRight format(3 elements): limitNum, destination, forced. Try again!'

            case CommandType.NO_OP:
                response = f"Cannot accept text messages for command {self.last_cmd.name}."

            case CommandType.POST:
                pass

            case CommandType.SIGNIN:
                result = await self.scout_client.sign_in(self.config.phone, message_text)
                if type(result) is telethon.types.User:
                    response = f"User signed in correctly."
                    self.last_cmd = CommandType.NO_OP
                else:
                    response = f'\nWrong auth code format. Try again!'

            case CommandType.SIGN_OUT:
                mess_to_lower = message_text.lower()
                match mess_to_lower:
                    case "yes":
                        response = ("Client successfully logged out. "
                                    "To use again the APIs please use /send_code and then /signin") \
                            if await self.scout_client.log_out() \
                            else "INTERNAL SERVER ERROR: could not log out correctly!"
                        self.last_cmd = CommandType.NO_OP
                    case "no":
                        response = "Operation cancelled. You're still authorized."
                        self.last_cmd = CommandType.NO_OP
                    case _:
                        response = "Answer not accepted. Accepted: (yes/no). . Try again!"

            case CommandType.STAT:
                dt: datetime = datetime.now()
                try:
                    if message_text != "today":
                        from dateutil import parser
                        dt = parser.parse(message_text)
                        if dt > datetime.now():
                            raise ValueError()

                    import aiofiles
                    path: str = f"./stat_{datetime.now()}.txt"
                    async with aiofiles.open(path, mode="w") as file:
                        await file.write(f"Statistics until {dt}:\n\n")
                        await file.write("id | username | created_at | invited_at\n\n")
                        user_info: persistence.User
                        for user_info in await UserManager.read_all(until_to=dt):
                            await file.write(f"{user_info.telegram_id} | {user_info.username} | "
                                             f"{user_info.created_at} | {user_info.invited_at}\n")

                    message_to_bot_admin = await update.message.reply_document(path)
                    if message_to_bot_admin is not None:
                        os.remove(path)
                        response = f"Download stat file complete."
                        self.last_cmd = CommandType.NO_OP
                    else:
                        response = "Error while downloading the stat file. Try again!"
                except (OverflowError, ValueError) as err:
                    response = f'{err}\nWrong date string format or limit. Try again!'
                except FileNotFoundError as err:
                    response = f"{err}"

            case CommandType.TOKEN_INIT:
                try:
                    self.bot_client = (TelegramClient('bot_user', self.config.api_id, self.config.api_hash)
                                       .start(bot_token=message_text))
                    response = "Bot user connected."
                    self.last_cmd = CommandType.NO_OP
                except ValueError as error:
                    logging.error(error)
                    response = f"{error}. Try again!"

        await update.message.reply_text(response)

    async def _token(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Please, write the bot token")
        self.last_cmd = CommandType.TOKEN_INIT

    async def _check_conn(self) -> str | None:
        """Returns `str` if the connection fails, else `None`"""

        if not self.scout_client.is_connected():
            try:
                await self.scout_client.connect()
            except OSError as os_error:
                return f"Failed to connect to telegram client {os_error}"
        return None

    async def _check_client(self) -> str | None:
        """Returns `str` if the user is not authorized or the connection fails, else `None`"""

        if not await self.scout_client.is_user_authorized():
            return "User not authorized. Please use /send_"
        if (res := await self._check_conn()) is not None:
            return res
        return None

    async def _search_dialog(self, message_text: str) -> Dialog | None:
        """Returns `int` (chat_id) if the user's chats name is `message_str` """

        dialog: Dialog
        async for dialog in self.scout_client.iter_dialogs():
            if dialog.name == message_text:
                return dialog
        return None
